"""EnterpriseOps Interwhen pipeline: generate -> review (+ repair) -> evaluate -> compare.

    python -m interwhen_eops generate [--policy ID ...]
    python -m interwhen_eops review [--policy ID ...] [--source DIR] [--out DIR]
    python -m interwhen_eops evaluate --arm baseline|interwhen (--split train|test | --task ID ...) --out DIR
    python -m interwhen_eops compare BASELINE_DIR INTERWHEN_DIR
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import evaluate, generate, review
from .utils import config
from .utils.data import load_split, select_documents


def main() -> None:
    """Parse the stage and its options, run it, and print its JSON summary."""
    work = config.runs_dir() / "pipeline"
    parser = argparse.ArgumentParser(prog="python -m interwhen_eops", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    stages = parser.add_subparsers(dest="stage", required=True)
    for name in ("generate", "review"):
        stage = stages.add_parser(name)
        stage.add_argument("--policy", nargs="*", default=[])
        stage.add_argument("--concurrency", type=int, default=3)
    stages.choices["review"].add_argument("--source", type=Path, default=work / "generated")
    stages.choices["review"].add_argument("--out", type=Path, default=work / "reviewed")
    run = stages.add_parser("evaluate")
    run.add_argument("--arm", choices=("baseline", "interwhen"), required=True)
    scope = run.add_mutually_exclusive_group(required=True)
    scope.add_argument("--split", choices=("train", "test"))
    scope.add_argument("--task", nargs="+")
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--policies", type=Path, default=config.POLICIES_DIR)
    run.add_argument("--concurrency", type=int, default=3)
    run.add_argument("--rerun-errors", action="store_true", help="retry tasks that hit connection errors")
    compare = stages.add_parser("compare")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("interwhen", type=Path)
    args = parser.parse_args()

    if args.stage == "generate":
        result = generate.run(select_documents(args.policy), work / "generated", work / "generate", args.concurrency)
    elif args.stage == "review":
        result = review.run(select_documents(args.policy), args.source, args.out, work / "review", args.concurrency)
    elif args.stage == "evaluate":
        if args.arm == "interwhen" and not any(args.policies.glob("*.json")):
            parser.error(f"no packages in {args.policies}")
        result = evaluate.run(args.task or load_split()[args.split], args.arm, args.out, args.policies,
                              args.concurrency, args.rerun_errors)
    else:
        result = evaluate.compare(args.baseline, args.interwhen, load_split()["train"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
