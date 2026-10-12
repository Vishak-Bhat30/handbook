"""Evaluation stage: run an arm over tasks, then summarize and compare arms.

An arm folder holds the gym's ``results_<task_id>.json`` files, their payloads and a
``run.json`` manifest. Existing results are skipped, so rerunning resumes.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from .utils import config, gym
from .utils.data import load_packages, load_tasks, policy_id, read_json, write_json

CONNECTION_ERROR = "Connection error."


def manifest(arm: str, policies_dir: Path) -> dict:
    """Configuration an arm folder was produced with (API key redacted)."""
    return {"arm": arm, "dataset_revision": config.DATASET_REVISION, "runtime": config.RUNTIME_VERSION,
            "scoring": config.SCORING_VERSION, "tool_contract": config.TOOL_CONTRACT,
            "agent": gym.agent_config(redact=True), "max_iterations": config.MAX_ITERATIONS,
            **({"extractor": config.model("extractor"), "planner": config.model("planner"),
                "plan_enabled": config.plan_enabled(), "plan_max_nudges": config.plan_max_nudges(),
                "policies": str(policies_dir)} if arm == "interwhen" else {})}


async def run_arm(tasks: list[dict], arm: str, out: Path, policies_dir: Path = config.POLICIES_DIR,
                  concurrency: int = 3) -> dict:
    """Run tasks in one arm, skipping tasks that already have results.

    Args:
        tasks: Dataset task rows.
        arm: ``"baseline"`` or ``"interwhen"``.
        out: Arm folder.
        policies_dir: Reviewed packages for the interwhen arm.
        concurrency: Tasks run at once.

    Returns:
        Summary from ``summarize``.

    Raises:
        ValueError: If the arm is unknown or ``out`` holds a different configuration.
    """
    if arm not in {"baseline", "interwhen"}:
        raise ValueError("arm must be baseline or interwhen")
    # The gym bridge changes the working directory, so pin paths first.
    out, policies_dir = out.resolve(), policies_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    expected = manifest(arm, policies_dir)
    if (out / "run.json").exists() and read_json(out / "run.json") != expected:
        raise ValueError(f"{out} was produced with a different configuration")
    write_json(out / "run.json", expected)
    gym_evaluate = gym.load_evaluate(load_packages(policies_dir) if arm == "interwhen" else None)
    limit = asyncio.Semaphore(concurrency)

    async def one(task):
        """Run one task within the concurrency limit."""
        async with limit:
            await gym.run_task(gym_evaluate, task, arm, out)

    await asyncio.gather(*(one(task) for task in tasks))
    return summarize(out)


def run(task_ids: list[str], arm: str, out: Path, policies_dir: Path = config.POLICIES_DIR,
        concurrency: int = 3, rerun_errors: bool = False) -> dict:
    """Evaluation stage for the given tasks.

    Args:
        task_ids: Dataset task IDs.
        arm: ``"baseline"`` or ``"interwhen"``.
        out: Arm folder.
        policies_dir: Reviewed packages for the interwhen arm.
        concurrency: Tasks run at once.
        rerun_errors: Archive connection-error results first so they run again.

    Returns:
        Summary from ``summarize``.
    """
    if rerun_errors:
        archive_errors(out)
    tasks = {task["task_id"]: task for task in load_tasks()}
    return asyncio.run(run_arm([tasks[task_id] for task_id in task_ids], arm, out, policies_dir, concurrency))


def outcomes(out: Path) -> dict[str, dict]:
    """Per-task outcome in an arm folder: success, error, policy, blocked calls and nudges."""
    found = {}
    for path in sorted(out.glob("results_*.json")):
        task_id = path.stem.removeprefix("results_")
        run = read_json(path)["runs"][0]
        audits = [step for step in run.get("conversation_flow", []) if step.get("type") == "interwhen_audit"]
        found[task_id] = {
            "success": run.get("overall_success"), "error": run.get("error"),
            "policy_id": policy_id(read_json(out / "payloads" / f"{task_id}.json")["system_prompt"]),
            "blocked_calls": audits[0]["blocked_calls"] if audits else None,
            "nudges": len(audits[0]["nudges"]) if audits else None}
    return found


def summarize(out: Path) -> dict:
    """Task, error and success counts with accuracy over non-errored tasks."""
    found = outcomes(out)
    valid = [item for item in found.values() if not item["error"]]
    successes = sum(item["success"] is True for item in valid)
    return {"tasks": len(found), "valid": len(valid), "successes": successes, "errors": len(found) - len(valid),
            "accuracy_valid": successes / len(valid) if valid else None}


def archive_errors(out: Path, message: str = CONNECTION_ERROR) -> list[str]:
    """Move results whose error contains ``message`` to ``_superseded`` so the next run retries them.

    Args:
        out: Arm folder.
        message: Error text identifying infrastructure failures.

    Returns:
        Task IDs archived.
    """
    moved, archive = [], out / "_superseded"
    for path in sorted(out.glob("results_*.json")):
        if message in str(read_json(path)["runs"][0].get("error") or ""):
            archive.mkdir(exist_ok=True)
            attempt = len(list(archive.glob(path.stem + ".*.json")))
            shutil.move(path, archive / f"{path.stem}.{attempt}.json")
            moved.append(path.stem.removeprefix("results_"))
    return moved


def compare(baseline: Path, interwhen: Path, train_ids=()) -> dict:
    """Paired comparison on tasks valid in both arms.

    Args:
        baseline: Baseline arm folder.
        interwhen: Interwhen arm folder.
        train_ids: Training task IDs; their losses select policies to re-review.

    Returns:
        Arm summaries, paired successes, gains, losses and ``regression_policies``.
    """
    left, right = outcomes(baseline), outcomes(interwhen)
    paired = sorted(task for task in set(left) & set(right) if not left[task]["error"] and not right[task]["error"])
    gains = [task for task in paired if right[task]["success"] and not left[task]["success"]]
    losses = [task for task in paired if left[task]["success"] and not right[task]["success"]]
    train = set(train_ids)
    return {"baseline": summarize(baseline), "interwhen": summarize(interwhen), "paired": len(paired),
            "baseline_paired_successes": sum(bool(left[task]["success"]) for task in paired),
            "interwhen_paired_successes": sum(bool(right[task]["success"]) for task in paired),
            "gains": gains, "losses": losses,
            "regression_policies": sorted({right[task]["policy_id"] for task in losses if task in train})}
