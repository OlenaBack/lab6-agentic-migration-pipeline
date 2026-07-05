"""
Build a Foundry evaluation dataset from the pipeline's extraction step.

One JSONL row per verified expectation. The row carries everything the
evaluator needs for a single judgment, mirroring the pipeline's
one-expectation-per-call design.

Usage (from the repo root, PYTHONPATH=src):

    python foundry/make_dataset.py --api-key-env OPENAI_API_KEY

Fail-closed: if extraction cannot validate, no dataset is written and the
script exits non-zero with the reason.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from functools import partial
from pathlib import Path

from core.file_io import read_source_file
from azure_llm_client import call_azure_llm
from extract_expectations.run import extract_expectations

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = REPO_ROOT / "workspace"

DEFAULT_SOURCE = WORKSPACE / "source" / "payroll-management.py"
DEFAULT_TARGET = WORKSPACE / "target" / "payroll-management.cs"
DEFAULT_OUTPUT = REPO_ROOT / "foundry" / "dataset.jsonl"

MIGRATION_RULES = """
Preserve the behavior of the original source.
Do not introduce unsupported behavior.
""".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    args = parser.parse_args()

    source = read_source_file(args.source)
    candidate = read_source_file(args.target)

    llm_call = call_azure_llm

    result = extract_expectations(
        source=source,
        llm_call=llm_call,
        migration_rules=MIGRATION_RULES,
    )

    if result.cannot_validate:
        print(f"Extraction declined: {result.reason}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for e in result.expectations:
            row = {
                "expectation_id": e.id,
                "category": e.category.value,
                "description": e.description,
                "evidence_quote": e.evidence_quote,
                "candidate": candidate,
                "source_path": str(args.source),
                "candidate_path": str(args.target),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(result.expectations)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())