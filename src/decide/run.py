from collections.abc import Sequence

from compare_candidate.contracts import FindingSeverity, FindingStatus, ValidationFinding
from decide.contracts import Decision


def decide(findings: Sequence[ValidationFinding]) -> Decision:
    """Deterministic: no LLM. Maps findings to a verdict."""
    if any(f.status == FindingStatus.UNCLEAR for f in findings):
        return Decision.HUMAN_REVIEW
    blocking = {FindingSeverity.CRITICAL, FindingSeverity.HIGH}
    if any(f.severity in blocking for f in findings):
        return Decision.REGENERATE
    return Decision.APPROVE
