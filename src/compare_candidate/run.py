from collections.abc import Callable, Sequence

from pydantic import ValidationError

from compare_candidate.contracts import (
    ComparisonJudgment,
    ComparisonStatus,
    FindingSeverity,
    FindingStatus,
    ValidationFinding,
)
from compare_candidate.prompt import build_prompt
from extract_expectations.contracts import ExpectedBehavior


# The LLM judges status only; severity is assigned deterministically so the
# downstream decide() step stays predictable. This map is intentionally coarse
# and can be refined later (e.g. category x status).
_STATUS_MAP = {
    ComparisonStatus.MISSING: FindingStatus.MISSING,
    ComparisonStatus.CHANGED: FindingStatus.CHANGED,
    ComparisonStatus.UNCLEAR: FindingStatus.UNCLEAR,
}
_SEVERITY_MAP = {
    FindingStatus.MISSING: FindingSeverity.HIGH,
    FindingStatus.CHANGED: FindingSeverity.HIGH,
    FindingStatus.UNCLEAR: FindingSeverity.MEDIUM,
}


def _unclear(expectation: ExpectedBehavior, rationale: str) -> ValidationFinding:
    """A safe fall-back finding when a judgment cannot be trusted or formed."""
    return ValidationFinding(
        expectation_id=expectation.id,
        status=FindingStatus.UNCLEAR,
        severity=FindingSeverity.MEDIUM,
        evidence_from_source=expectation.evidence_quote,
        rationale=rationale,
    )


def compare_candidate(
    candidate: str,
    expectations: Sequence[ExpectedBehavior],
    llm_call: Callable[[str], str],
) -> list[ValidationFinding]:
    """
    Recall check: for each expectation, decide whether the candidate preserves
    it. PRESERVED produces no finding; everything else becomes a grounded
    ValidationFinding. One expectation per call (batching lowers recall).

    A non-empty candidate is required; ensuring the target exists is the input
    gate's job, so an empty candidate is a wiring error and raises rather than
    being mistaken for "nothing diverged".
    """

    if not candidate or not candidate.strip():
        raise ValueError(
            "compare_candidate requires a non-empty candidate; the input gate "
            "should confirm the target is present before comparison."
        )

    if not expectations:
        raise ValueError(
            "compare_candidate requires at least one expectation; an empty "
            "sequence means extraction was skipped, which is a wiring error."
        )

    findings: list[ValidationFinding] = []

    for expectation in expectations:
        prompt = build_prompt(expectation.description, expectation.evidence_quote, candidate)

        try:
            response = llm_call(prompt)
        except Exception:
            findings.append(_unclear(expectation, "The comparison LLM call failed."))
            continue

        if not response or not response.strip():
            findings.append(
                _unclear(expectation, "The comparison LLM returned an empty response.")
            )
            continue

        try:
            judgment = ComparisonJudgment.model_validate_json(response)
        except ValidationError:
            findings.append(
                _unclear(
                    expectation,
                    "The comparison response did not match the expected schema.",
                )
            )
            continue

        if judgment.status == ComparisonStatus.PRESERVED:
            continue

        finding_status = _STATUS_MAP[judgment.status]
        candidate_evidence = (judgment.evidence_from_candidate or "").strip() or None

        try:
            findings.append(
                ValidationFinding(
                    expectation_id=expectation.id,
                    status=finding_status,
                    severity=_SEVERITY_MAP[finding_status],
                    evidence_from_source=expectation.evidence_quote,
                    evidence_from_candidate=candidate_evidence,
                    rationale=judgment.rationale,
                )
            )
        except ValidationError:
            # e.g. a CHANGED verdict with no candidate evidence: the finding
            # contract forbids it, so we degrade to a coherent UNCLEAR.
            findings.append(
                _unclear(
                    expectation,
                    "The comparison judgment was incomplete "
                    "(a non-preserved verdict without usable candidate evidence).",
                )
            )

    return findings
