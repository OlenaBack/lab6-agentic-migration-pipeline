"""
Verdict gate over Foundry evaluation results.

Foundry aggregates per-row scores (averages, pass rates); it has no native
cross-row gate. This module restores the pipeline's deterministic decision:
it converts evaluator rows back into ValidationFindings using the repo's own
status/severity maps and calls the real decide().

Fail-closed, in two layers:
- A row with a recognizable status but an incomplete judgment degrades to an
  UNCLEAR finding (same as compare_candidate does).
- A row that cannot be represented as a contract-valid finding at all
  (unrecognizable status, missing expectation reference) short-circuits the
  verdict to HUMAN_REVIEW; the finding contract is never bent to fit it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import ValidationError

from compare_candidate.contracts import (
    ComparisonStatus,
    FindingSeverity,
    FindingStatus,
    ValidationFinding,
)
from compare_candidate.run import _SEVERITY_MAP, _STATUS_MAP
from decide.contracts import Decision, ValidationVerdict
from decide.run import decide

_PRESERVED = object()  # sentinel: row is fine, produces no finding
_UNUSABLE = object()   # sentinel: row cannot become a contract-valid finding


def _finding_from_row(row: Mapping[str, object]) -> ValidationFinding | object:
    expectation_id = str(row.get("expectation_id") or "") or None
    source_evidence = str(row.get("evidence_quote") or "") or None

    try:
        status = ComparisonStatus(str(row.get("status") or ""))
    except ValueError:
        return _UNUSABLE

    if status == ComparisonStatus.PRESERVED:
        return _PRESERVED

    finding_status = _STATUS_MAP[status]
    candidate_evidence = str(row.get("evidence_from_candidate") or "").strip() or None
    rationale = str(row.get("rationale") or "").strip() or "No rationale provided."

    try:
        return ValidationFinding(
            expectation_id=expectation_id,
            status=finding_status,
            severity=_SEVERITY_MAP[finding_status],
            evidence_from_source=source_evidence,
            evidence_from_candidate=candidate_evidence,
            rationale=rationale,
        )
    except ValidationError:
        pass

    # Degrade to UNCLEAR, exactly as compare_candidate does for incomplete
    # judgments. If even that violates the contract (e.g. no expectation
    # reference at all), the row is unusable.
    try:
        return ValidationFinding(
            expectation_id=expectation_id,
            status=FindingStatus.UNCLEAR,
            severity=FindingSeverity.MEDIUM,
            evidence_from_source=source_evidence,
            rationale="Incomplete judgment (non-preserved without usable evidence).",
        )
    except ValidationError:
        return _UNUSABLE


def verdict_from_rows(
    rows: Iterable[Mapping[str, object]],
    source_path: str,
    candidate_path: str,
) -> ValidationVerdict:
    findings: list[ValidationFinding] = []
    unusable = 0

    for row in rows:
        result = _finding_from_row(row)
        if result is _PRESERVED:
            continue
        if result is _UNUSABLE:
            unusable += 1
            continue
        findings.append(result)

    decision = decide(findings)
    if unusable:
        decision = Decision.HUMAN_REVIEW  # fail-closed: never approve past junk

    return ValidationVerdict(
        decision=decision,
        source_path=source_path,
        candidate_path=candidate_path,
        checks_performed=("comparison",),
        finding_count=len(findings) + unusable,
    )


__all__ = ["Decision", "ValidationVerdict", "verdict_from_rows"]