from enum import Enum

from pydantic import model_validator

from core.base import ContractModel, NonEmptyText


class ComparisonStatus(str, Enum):
    PRESERVED = "preserved"
    MISSING = "missing"
    CHANGED = "changed"
    UNCLEAR = "unclear"


class ComparisonJudgment(ContractModel):
    status: ComparisonStatus
    evidence_from_candidate: str | None = None
    rationale: NonEmptyText


class FindingStatus(str, Enum):
    MISSING = "missing"
    CHANGED = "changed"
    ADDED = "added"
    UNCLEAR = "unclear"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationFinding(ContractModel):
    expectation_id: str | None = None
    status: FindingStatus
    severity: FindingSeverity
    evidence_from_source: str | None = None
    evidence_from_candidate: str | None = None
    rationale: NonEmptyText

    @model_validator(mode="after")
    def validate_shape(self) -> "ValidationFinding":
        if self.status == FindingStatus.ADDED:
            if self.expectation_id is not None:
                raise ValueError("An ADDED finding cannot reference an expectation.")
            if self.evidence_from_source is not None:
                raise ValueError("An ADDED finding cannot cite source evidence.")
            if not self.evidence_from_candidate:
                raise ValueError("An ADDED finding must cite candidate evidence.")
            return self
        if self.expectation_id is None:
            raise ValueError(f"A {self.status.value} finding must reference an expectation.")
        if not self.evidence_from_source:
            raise ValueError(f"A {self.status.value} finding must cite source evidence.")
        if self.status == FindingStatus.CHANGED and not self.evidence_from_candidate:
            raise ValueError("A CHANGED finding must cite candidate evidence.")
        return self
