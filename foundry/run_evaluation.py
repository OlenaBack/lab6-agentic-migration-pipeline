"""
Run the faithfulness evaluation over the dataset and compute the verdict.

Local execution: azure-ai-evaluation orchestrates rows -> evaluator calls,
writes per-row results, and this script feeds them into the deterministic
verdict gate (the repo's real decide()).
"""

from __future__ import annotations

import json
from pathlib import Path

from azure.ai.evaluation import evaluate

from azure_llm_client import call_azure_llm
from faithfulness_evaluator import FaithfulnessEvaluator
from verdict import verdict_from_rows

FOUNDRY_DIR = Path(__file__).resolve().parent
DATASET = FOUNDRY_DIR / "dataset.jsonl"
RESULTS = FOUNDRY_DIR / "evaluation_results.json"


def main() -> int:
    result = evaluate(
        data=str(DATASET),
         evaluators={"faithfulness": FaithfulnessEvaluator(call_azure_llm)},
        azure_ai_project="https://matrona-foundry.services.ai.azure.com/api/projects/legacy-code-migration-validation",
        evaluator_config={
            "faithfulness": {
                "column_mapping": {
                    "description": "${data.description}",
                    "evidence_quote": "${data.evidence_quote}",
                    "candidate": "${data.candidate}",
                    "expectation_id": "${data.expectation_id}",
                }
            }
        },
        output_path=str(RESULTS),
    )

    print("Metrics:", json.dumps(result.get("metrics", {}), indent=2))

    # Flatten evaluate() rows into the shape verdict_from_rows expects.
    rows = []
    for row in result.get("rows", []):
        rows.append(
            {
                "expectation_id": row.get("outputs.faithfulness.expectation_id")
                or row.get("inputs.expectation_id"),
                "status": row.get("outputs.faithfulness.status"),
                "rationale": row.get("outputs.faithfulness.rationale"),
                "evidence_from_candidate": row.get(
                    "outputs.faithfulness.evidence_from_candidate"
                ),
                "evidence_quote": row.get("inputs.evidence_quote"),
            }
        )

    first = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])
    verdict = verdict_from_rows(
        rows,
        source_path=first["source_path"],
        candidate_path=first["candidate_path"],
    )

    print("\n=== ValidationVerdict ===")
    print(verdict.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())