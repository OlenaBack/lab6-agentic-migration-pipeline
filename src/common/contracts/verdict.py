from enum import Enum

from common.contracts.base import ContractModel


class Decision(str, Enum):
    APPROVE = "approve"
    REGENERATE = "regenerate"
    HUMAN_REVIEW = "human_review"


class ValidationVerdict(ContractModel):
    decision: Decision
    source_path: str
    candidate_path: str
    checks_performed: tuple[str, ...]
    finding_count: int