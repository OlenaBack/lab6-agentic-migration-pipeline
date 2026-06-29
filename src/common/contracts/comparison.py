from enum import Enum

from pydantic import Field

from common.contracts.base import ContractModel


class ComparisonStatus(str, Enum):
    PRESERVED = "preserved"
    MISSING = "missing"
    CHANGED = "changed"
    UNCLEAR = "unclear"


class ComparisonJudgment(ContractModel):
    status: ComparisonStatus
    evidence_from_candidate: str | None = None
    rationale: str = Field(min_length=1)