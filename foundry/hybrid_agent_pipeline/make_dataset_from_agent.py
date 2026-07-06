"""
Build the evaluation dataset with extraction performed by the Foundry
prompt agent (expectation-extractor) instead of a direct model call.

The agent carries the extraction instructions; this script sends only the
variable part (migration rules + source) as the user message — the same
input shape as the portal playground test. All verification, ID
assignment, and fail-closed behavior are the repo's own
extract_expectations(); only the llm_call is swapped.

Requires:
    az login                       (Entra ID; API keys are not accepted)
    FOUNDRY_PROJECT_ENDPOINT       e.g. https://matrona-foundry.services.ai.azure.com/api/projects/legacy-code-migration-validation
    Azure AI User role on the project.

Usage (repo root, PYTHONPATH=src;foundry):
    python foundry/make_dataset_from_agent.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from core.file_io import read_source_file
from extract_expectations.run import extract_expectations

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = REPO_ROOT / "workspace"

DEFAULT_SOURCE = WORKSPACE / "source" / "payroll-management.py"
DEFAULT_TARGET = WORKSPACE / "target" / "payroll-management.cs"
DEFAULT_OUTPUT = REPO_ROOT / "foundry" / "dataset_v2.jsonl"

AGENT_NAME = "expectation-extractor"
AGENT_VERSION = os.environ.get("EXTRACTOR_AGENT_VERSION", "").strip() or None

MIGRATION_RULES = """
Preserve the behavior of the original source.
Do not introduce unsupported behavior.
""".strip()


def _project_client() -> OpenAI:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is not set.")
    return OpenAI(
        base_url=endpoint.rstrip("/") + "/openai/v1",
        api_key=get_bearer_token_provider(
            DefaultAzureCredential(), "https://ai.azure.com/.default"
        ),
    )


def make_agent_llm_call(source: str, rules: str):
    """
    Return an llm_call for extract_expectations() backed by the agent.

    extract_expectations() passes in a fully built prompt that already
    contains the extraction instructions. The agent carries those same
    instructions in its definition, so sending the full prompt would
    duplicate them. This callable therefore ignores the built prompt and
    sends only the variable payload (rules + source) — byte-for-byte the
    same user message the agent was tested with in the portal playground.
    """

    client = _project_client()
    user_message = (
        "MIGRATION RULES:\n"
        f"{rules}\n\n"
        "SOURCE CODE:\n"
        "--- SOURCE START ---\n"
        f"{source}\n"
        "--- SOURCE END ---"
    )

    agent_reference: dict[str, str] = {
        "type": "agent_reference",
        "name": AGENT_NAME,
    }
    if AGENT_VERSION:
        agent_reference["version"] = AGENT_VERSION

    def llm_call(_prompt: str) -> str:
        response = client.responses.create(
            input=user_message,
            extra_body={"agent_reference": agent_reference},
        )
        return response.output_text.strip()

    return llm_call


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = read_source_file(args.source)
    candidate = read_source_file(args.target)

    result = extract_expectations(
        source=source,
        llm_call=make_agent_llm_call(source, MIGRATION_RULES),
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