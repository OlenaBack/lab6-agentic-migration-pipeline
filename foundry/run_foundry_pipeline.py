"""
Run the validation pipeline with all LLM stages executing in Foundry.

Stages:
  1. Extraction   - Foundry expectation-extractor agent, run
                    EXTRACTION_PASSES times; the rubric is the union of
                    grounded expectations across passes.
  2. Verification - the repo's own extract_expectations(): verbatim
                    grounding, fail-closed; ID assignment happens once
                    over the union.
  3. Comparison   - Foundry behavior-comparison-agent, one call per
                    expectation, returning full ComparisonJudgments
                    including evidence_from_candidate. These rows are
                    AUTHORITATIVE for the verdict.
  4. Evaluation   - cloud evaluation with an inline label_model grader
                    (faithfulness-label) over the uploaded dataset. Kept
                    as the observability layer: portal-visible run,
                    metrics, and an independent second judging used as a
                    cross-check.
  5. Verdict      - the repo's own decide(), via verdict_from_rows(),
                    over the agent rows. Where the evaluator's label
                    (when usable) disagrees with the agent's status, the
                    row is downgraded to UNCLEAR before the verdict: two
                    judges disagreeing is exactly the ambiguity human
                    review exists for.

Why union-of-N extraction: extraction is the pipeline's nondeterministic
stage and its variance is a recall gap — an unextracted behavior cannot
be judged, and a sparse pass can silently approve a defective candidate
(observed: single passes produced 5, 9, 7, 8, 8, and 6 expectations from
identical inputs; the 6-expectation pass missed both seeded defects and
yielded a false APPROVE). Verification makes the union safe by
construction — no ungrounded draft can enter regardless of how many
passes run — so recall can only improve.

Judge prompt note: both judges (comparison agent instructions in the
portal and the evaluator prompt below) must carry the same v2 rules
(exception types are observable behavior; no speculative precision
flags). Runs are not comparable with pre-v2 runs.

Known mechanism note: the evaluator grader cannot return
evidence_from_candidate; that is why the agent rows, which can, are
authoritative. The platform's label extraction can also return
label=None even when the judge answered correctly (observed with
gpt-5-nano); _label_from_result() falls back to parsing the judge's own
JSON answer, and rows that stay unusable are logged but excluded from
the cross-check rather than failing the run.

Requires: az login; FOUNDRY_PROJECT_ENDPOINT; Foundry User role;
optional EXTRACTOR_AGENT_VERSION, COMPARISON_AGENT_VERSION,
EXTRACTION_PASSES (default 3);
pip install azure-ai-projects azure-identity openai.

Usage (repo root, PYTHONPATH=src;foundry):
    python foundry/run_foundry_pipeline.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

from behavior_comparison_agent import compare_behavior
from core.file_io import read_source_file
from extract_expectations.run import extract_expectations
from make_dataset_from_agent import MIGRATION_RULES, make_agent_llm_call
from verdict import verdict_from_rows

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "workspace" / "source" / "payroll-management.py"
TARGET = Path(os.environ.get( 
    "CANDIDATE_PATH",
    str(REPO_ROOT / "workspace" / "target" / "payroll-management.cs"),
))
OUT_DIR = REPO_ROOT / "foundry"

EVALUATOR_NAME = "faithfulness-label"
JUDGE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5-nano")
POLL_SECONDS = 10
TIMEOUT_SECONDS = 600
EXTRACTION_PASSES = max(1, int(os.environ.get("EXTRACTION_PASSES", "3")))

VALID_LABELS = {"preserved", "missing", "changed", "unclear"}

SYSTEM_PROMPT = (
    "You compare a migrated code CANDIDATE against ONE expected behavior "
    "taken from the original source.\n\n"
    "Decide whether the candidate preserves this single behavior, and "
    "answer with exactly one label:\n\n"
    "- preserved: the candidate clearly does the same thing.\n"
    "- missing: the behavior is absent from the candidate.\n"
    "- changed: the behavior is present but differs (different type, "
    "value, rounding, exception raised, return shape, ...).\n"
    "- unclear: the candidate does not provide enough to decide.\n\n"
    "Rules:\n"
    "- Judge only this one expectation, not the whole file.\n"
    "- Exception types are part of observable behavior. If the source "
    "and candidate raise different exception types, label the behavior "
    "as changed, even when the condition and message match.\n"
    "- Judge observable behavior, not syntax or numeric representation "
    "alone.\n"
    "- Mark a numeric representation difference as changed only when a "
    "concrete supported input produces a different observable result.\n"
    "- Do not mark behavior as changed based only on a speculative "
    "precision risk.\n"
    "- Do not approve or reject the migration. Judge only this behavior."
)

USER_PROMPT = (
    "EXPECTED BEHAVIOR:\n{{item.description}}\n\n"
    "SOURCE EVIDENCE FOR THIS BEHAVIOR:\n{{item.evidence_quote}}\n\n"
    "MIGRATED CANDIDATE:\n"
    "--- CANDIDATE START ---\n"
    "{{item.candidate}}\n"
    "--- CANDIDATE END ---"
)


def _normalize_quote(quote: str) -> str:
    """Whitespace-normalized form of an evidence quote (dedup key)."""
    return " ".join(quote.split())


def extract_expectations_union(source: str, rules: str, passes: int):
    """
    Run the extraction agent `passes` times, verify each pass with the
    repo's own extract_expectations(), and union the grounded
    expectations across passes (dedup by normalized evidence quote,
    first-seen description/category wins). IDs are re-assigned once over
    the union, in first-seen order, so identity stays code-owned.

    Fail-closed: if every pass declines, the union declines with the
    collected reasons.
    """
    from extract_expectations.contracts import ExpectedBehavior

    seen: dict[str, "ExpectedBehavior"] = {}
    reasons: list[str] = []
    for attempt in range(1, passes + 1):
        result = extract_expectations(
            source=source,
            llm_call=make_agent_llm_call(source, rules),
            migration_rules=rules,
        )
        if result.cannot_validate:
            reasons.append(f"pass {attempt}: {result.reason}")
            print(f"      pass {attempt}/{passes}: declined "
                  f"({result.reason})")
            continue
        new = 0
        for e in result.expectations:
            key = _normalize_quote(e.evidence_quote)
            if key not in seen:
                seen[key] = e
                new += 1
        print(f"      pass {attempt}/{passes}: "
              f"{len(result.expectations)} verified, {new} new")

    if not seen:
        return None, "; ".join(reasons) or "all extraction passes declined"

    merged = [
        ExpectedBehavior(
            id=f"EXP-{index:03d}",
            description=e.description,
            category=e.category,
            evidence_quote=e.evidence_quote,
        )
        for index, e in enumerate(seen.values(), start=1)
    ]
    return merged, None


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _label_from_result(result: dict) -> tuple[str, str]:
    """
    Read the evaluator's extracted label; if the platform failed to
    extract one, fall back to parsing the judge's own JSON answer
    ("result" key). Returns (label, rationale); an empty label means the
    row is unusable for the cross-check.
    """
    label = str(result.get("label") or "").strip().lower()
    if label in VALID_LABELS:
        return label, str(result.get("reason") or "")

    sample = result.get("sample") or {}
    for message in sample.get("output") or []:
        content = message.get("content") if isinstance(message, dict) else None
        try:
            parsed = json.loads(content)
        except (TypeError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        label = str(parsed.get("result") or "").strip().lower()
        if label in VALID_LABELS:
            steps = parsed.get("steps") or []
            reason = "; ".join(
                str(s.get("conclusion") or "")
                for s in steps
                if isinstance(s, dict) and s.get("conclusion")
            )
            return label, reason
    return "", ""


def main() -> int:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        print("FOUNDRY_PROJECT_ENDPOINT is not set.", file=sys.stderr)
        return 2

    run_id = stamp()
    source = read_source_file(SOURCE)
    candidate = read_source_file(TARGET)

    # ---- Stage 1 + 2: agent extraction (union of N), verification -----
    print(f"[1/5] Extracting via Foundry agent "
          f"({EXTRACTION_PASSES} passes, union)...")
    expectations, decline_reason = extract_expectations_union(
        source, MIGRATION_RULES, EXTRACTION_PASSES
    )
    if expectations is None:
        print(f"Extraction declined: {decline_reason}", file=sys.stderr)
        print("Verdict: human_review (fail-closed, no rubric).")
        return 1
    print(f"      union rubric: {len(expectations)} expectations.")

    # ---- Stage 3: comparison agent (authoritative judgments) ----------
    print("[2/5] Comparing via Foundry agent...")
    agent_rows = []
    for index, e in enumerate(expectations, start=1):
        judgment = compare_behavior(
            expectation_id=e.id,
            description=e.description,
            evidence_quote=e.evidence_quote,
            candidate=candidate,
        )
        agent_rows.append({
            "expectation_id": e.id,
            "status": judgment.status.value,
            "rationale": judgment.rationale,
            "evidence_from_candidate": judgment.evidence_from_candidate or "",
            "evidence_quote": e.evidence_quote,
        })
        print(f"      [{index}/{len(expectations)}] "
              f"{e.id} -> {judgment.status.value}")

    # ---- Stage 4: dataset upload + cloud evaluation (observability) ---
    dataset_path = OUT_DIR / f"dataset_pipeline_{run_id}.jsonl"
    with dataset_path.open("w", encoding="utf-8") as f:
        for e in expectations:
            f.write(json.dumps({
                "expectation_id": e.id,
                "category": e.category.value,
                "description": e.description,
                "evidence_quote": e.evidence_quote,
                "candidate": candidate,
                "source_path": str(SOURCE),
                "candidate_path": str(TARGET),
            }, ensure_ascii=False) + "\n")

    print("[3/5] Uploading dataset to Foundry...")
    project = AIProjectClient(
        endpoint=endpoint, credential=DefaultAzureCredential()
    )
    dataset = project.datasets.upload_file(
        name="payroll-rubric-pipeline",
        version=run_id,
        file_path=str(dataset_path),
    )
    openai_client = project.get_openai_client()

    print("[4/5] Creating cloud evaluation run...")
    eval_object = openai_client.evals.create(
        name=f"payroll-pipeline-{run_id}",
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "expectation_id": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "candidate": {"type": "string"},
                },
                "required": [
                    "expectation_id", "description",
                    "evidence_quote", "candidate",
                ],
            },
        },
        testing_criteria=[{
            "type": "label_model",
            "name": EVALUATOR_NAME,
            "model": JUDGE_DEPLOYMENT,
            "input": [
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT},
            ],
            "labels": ["preserved", "missing", "changed", "unclear"],
            "passing_labels": ["preserved"],
        }],
    )
    print(f"      Eval {eval_object.id}")
    run = openai_client.evals.runs.create(
        eval_id=eval_object.id,
        name=f"run-{run_id}",
        data_source={
            "type": "jsonl",
            "source": {"type": "file_id", "id": dataset.id},
        },
    )
    print(f"      Run {run.id} started; polling...")

    deadline = time.time() + TIMEOUT_SECONDS
    while True:
        run = openai_client.evals.runs.retrieve(
            eval_id=eval_object.id, run_id=run.id
        )
        if run.status in ("completed", "failed", "canceled"):
            break
        if time.time() > deadline:
            break
        time.sleep(POLL_SECONDS)

    eval_rows: dict[str, str] = {}
    if run.status == "completed":
        items = openai_client.evals.runs.output_items.list(
            eval_id=eval_object.id, run_id=run.id
        )
        for item in items:
            data = (
                item.model_dump() if hasattr(item, "model_dump")
                else dict(item)
            )
            src_item = data.get("datasource_item", {}) or {}
            grader = next(
                (r for r in data.get("results", []) or []
                 if isinstance(r, dict)
                 and (r.get("name") == EVALUATOR_NAME
                      or r.get("metric") == EVALUATOR_NAME)),
                {},
            )
            label, _ = _label_from_result(grader)
            if label:
                eval_rows[str(src_item.get("expectation_id"))] = label
    else:
        print(f"      Evaluation ended '{run.status}'; continuing with "
              "agent judgments only (cross-check unavailable).",
              file=sys.stderr)

    # ---- Stage 5: cross-check + deterministic verdict ------------------
    NON_PRESERVED = {"changed", "missing"}
    print("[5/5] Cross-checking and computing verdict...")
    final_rows = []
    for row in agent_rows:
        eval_label = eval_rows.get(row["expectation_id"], "")
        same_side = (
            eval_label == row["status"]
            or (eval_label in NON_PRESERVED
                and row["status"] in NON_PRESERVED)
        )
        if eval_label and not same_side:
            print(f"      DISAGREEMENT {row['expectation_id']}: "
                  f"agent={row['status']} evaluator={eval_label} "
                  "-> unclear")
            row = {
                **row,
                "status": "unclear",
                "rationale": (
                    f"Judges disagree (agent: {row['status']}, "
                    f"evaluator: {eval_label}). {row['rationale']}"
                ),
                "evidence_from_candidate": "",
            }
        elif eval_label and eval_label != row["status"]:
            print(f"      taxonomy note {row['expectation_id']}: "
                  f"agent={row['status']} evaluator={eval_label} "
                  "(same side, agent kept)")
        final_rows.append(row)
    results_path = OUT_DIR / f"pipeline_results_{run_id}.json"
    results_path.write_text(
        json.dumps(
            {"agent_rows": agent_rows,
             "evaluator_labels": eval_rows,
             "final_rows": final_rows},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    verdict = verdict_from_rows(final_rows, str(SOURCE), str(TARGET))
    print("\n=== ValidationVerdict (Foundry pipeline) ===")
    print(verdict.model_dump_json(indent=2))
    print(f"\nRows: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())