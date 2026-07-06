"""
FaithfulnessEvaluator: a custom evaluator for azure-ai-evaluation.

One call = one (expectation, candidate) judgment, reusing the pipeline's
real comparison prompt and ComparisonJudgment contract. The evaluator never
raises for LLM or schema failures: it degrades to "unclear" so the verdict
gate can route the row to human review (fail-closed).

The LLM judges status only. Severity and the final verdict are assigned
downstream by deterministic code (see verdict.py), preserving the
LLM-proposes / code-decides boundary.

Output columns per row:
    status     preserved | missing | changed | unclear
    preserved  1.0 / 0.0  (numeric, so Foundry can aggregate a pass rate)
    rationale, evidence_from_candidate, degraded_reason
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError

from compare_candidate.contracts import ComparisonJudgment, ComparisonStatus
from compare_candidate.prompt import build_prompt


class FaithfulnessEvaluator:
    """Callable evaluator: judges whether the candidate preserves one behavior."""

    def __init__(self, llm_call: Callable[[str], str]):
        self._llm_call = llm_call

    def __call__(
        self,
        *,
        description: str,
        evidence_quote: str,
        candidate: str,
        expectation_id: str = ""
    ) -> dict:
        prompt = build_prompt(description, evidence_quote, candidate)

        try:
            response = self._llm_call(prompt)
        except Exception as exc:  # fail-closed, never raise
            return self._unclear(expectation_id, f"LLM call failed: {exc}")

        if not response or not response.strip():
            return self._unclear(expectation_id, "LLM returned an empty response.")

        try:
            judgment = ComparisonJudgment.model_validate_json(response)
        except ValidationError:
            return self._unclear(
                expectation_id, "Response did not match the judgment schema."
            )

        return {
            "expectation_id": expectation_id,
            "status": judgment.status.value,
            "preserved": 1.0 if judgment.status == ComparisonStatus.PRESERVED else 0.0,
            "rationale": judgment.rationale,
            "evidence_from_candidate": judgment.evidence_from_candidate or "",
            "degraded_reason": "",
        }

    @staticmethod
    def _unclear(expectation_id: str, reason: str) -> dict:
        return {
            "expectation_id": expectation_id,
            "status": ComparisonStatus.UNCLEAR.value,
            "preserved": 0.0,
            "rationale": reason,
            "evidence_from_candidate": "",
            "degraded_reason": reason,
        }