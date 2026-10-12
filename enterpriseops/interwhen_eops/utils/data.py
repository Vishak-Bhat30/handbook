"""Dataset tasks, policy identity, the train/test split and package storage."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from . import config


def policy_id(text: str) -> str:
    """Stable identifier of a policy text.

    Args:
        text: Policy (task system prompt); whitespace differences are ignored.

    Returns:
        First 12 hex digits of the SHA-256 of the normalized text.
    """
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()[:12]


def read_json(path):
    """Load a UTF-8 JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data) -> None:
    """Atomically write ``data`` as indented UTF-8 JSON, creating parent folders."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_tasks(domains=config.DOMAINS) -> list[dict]:
    """Load dataset tasks at the pinned revision.

    Args:
        domains: Dataset splits to load.

    Returns:
        Task rows with ``domain`` added and JSON string fields decoded.
    """
    from datasets import load_dataset

    tasks = []
    for domain in domains:
        for row in load_dataset(config.DATASET, "oracle", split=domain, revision=config.DATASET_REVISION):
            task = {**dict(row), "domain": domain}
            for key in ("gym_servers_config", "verifiers"):
                if isinstance(task.get(key), str):
                    task[key] = json.loads(task[key])
            tasks.append(task)
    return tasks


def policy_documents(tasks, train_ids=()) -> dict[str, dict]:
    """Group tasks by source policy.

    Args:
        tasks: Task rows from ``load_tasks``.
        train_ids: Training task IDs to record per policy.

    Returns:
        Policy ID to ``{policy, tools, domains, train_ids}``.
    """
    train, documents = set(train_ids), {}
    for task in sorted(tasks, key=lambda item: item["task_id"]):
        document = documents.setdefault(policy_id(task["system_prompt"]),
            {"policy": task["system_prompt"], "tools": set(), "domains": set(), "train_ids": []})
        document["tools"].update(task.get("selected_tools") or [])
        document["domains"].add(task["domain"])
        if task["task_id"] in train:
            document["train_ids"].append(task["task_id"])
    return {owner: {**document, "tools": sorted(document["tools"]), "domains": sorted(document["domains"])}
            for owner, document in documents.items()}


def proportional_split(tasks, seed: int, forced_train=(), train_domains=("teams", "csm", "hr"),
                       train_size: int = 130) -> dict:
    """Draw a domain-proportional training sample (largest remainder) from ``train_domains``.

    Args:
        tasks: All dataset tasks; those not sampled form the test split.
        seed: Sampling seed.
        forced_train: Task IDs that must be in training (counted in their domain quota).
        train_domains: Domains eligible for training.
        train_size: Number of training tasks.

    Returns:
        Split record with sorted ``train`` and ``test`` task IDs.

    Raises:
        ValueError: If IDs repeat, a domain is missing, or forced IDs exceed their quota.
    """
    domains = defaultdict(list)
    for task in tasks:
        domains[task["domain"]].append(task["task_id"])
    ids = [task["task_id"] for task in tasks]
    if len(set(ids)) != len(ids) or set(train_domains) - domains.keys():
        raise ValueError("Tasks need unique IDs and every training domain")
    eligible = sum(len(domains[domain]) for domain in train_domains)
    quotas = {domain: train_size * len(domains[domain]) // eligible for domain in train_domains}
    ranked = sorted(train_domains, key=lambda domain: (-(train_size * len(domains[domain]) % eligible), domain))
    for domain in ranked[:train_size - sum(quotas.values())]:
        quotas[domain] += 1
    forced = set(forced_train)
    if any(len(forced.intersection(domains[domain])) > quotas[domain] for domain in train_domains) or \
            forced - {task_id for domain in train_domains for task_id in domains[domain]}:
        raise ValueError("Forced training IDs must fit their domain quotas")
    generator, train = random.Random(seed), set(forced)
    for domain in sorted(train_domains):
        available = sorted(set(domains[domain]) - forced)
        train.update(generator.sample(available, quotas[domain] - len(forced.intersection(domains[domain]))))
    return {"dataset": config.DATASET, "dataset_revision": config.DATASET_REVISION, "seed": seed,
            "train_domains": sorted(train_domains), "train_size": train_size, "forced_train_ids": sorted(forced),
            "train": sorted(train), "test": sorted(set(ids) - train)}


def load_split(path=config.SPLIT_PATH) -> dict:
    """Load the frozen train/test split."""
    return read_json(path)


def load_packages(directory=config.POLICIES_DIR) -> dict[str, dict]:
    """Load policy packages.

    Args:
        directory: Folder of ``<policy_id>.json`` packages.

    Returns:
        Policy ID to package.
    """
    return {path.stem: read_json(path) for path in sorted(Path(directory).glob("*.json"))}


def select_documents(policy_ids=()) -> dict[str, dict]:
    """Policy documents for the pipeline, with training IDs from the frozen split.

    Args:
        policy_ids: Policies to keep; empty selects all.

    Returns:
        Policy ID to document, as in ``policy_documents``.

    Raises:
        ValueError: If a requested policy ID is not in the dataset.
    """
    documents = policy_documents(load_tasks(), load_split()["train"])
    unknown = set(policy_ids) - set(documents)
    if unknown:
        raise ValueError(f"Unknown policy IDs: {sorted(unknown)}")
    return {owner: documents[owner] for owner in (policy_ids or sorted(documents))}
