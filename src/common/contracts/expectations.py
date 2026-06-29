from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from common.contracts.base import ContractModel


NonEmptyText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


class ExpectationCategory(str, Enum):
    INPUT = "input"
    CALCULATION = "calculation"
    OUTPUT = "output"
    ERROR = "error"
    SIDE_EFFECT = "side-effect"


class ExpectationDraft(ContractModel):
    """
    Untrusted expectation returned by the LLM.

    The structure is valid, but the evidence quote has not yet
    been verified against the original source.
    """

    description: NonEmptyText
    category: ExpectationCategory
    evidence_quote: NonEmptyText


class ExpectationExtractionPayload(ContractModel):
    """
    Untrusted structured response returned by the LLM.

    It represents either:

    1. a successful extraction with one or more drafts; or
    2. an explicit inability to validate, including a reason.
    """

    expectations: list[ExpectationDraft] = Field(default_factory=list)
    cannot_validate: bool = False
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ExpectationExtractionPayload:
        if self.cannot_validate:
            if self.expectations:
                raise ValueError(
                    "cannot_validate cannot carry expectations."
                )

            if self.reason is None:
                raise ValueError(
                    "cannot_validate must include a reason."
                )

            return self

        if not self.expectations:
            raise ValueError(
                "A successful extraction must contain at least one expectation."
            )

        if self.reason is not None:
            raise ValueError(
                "A successful extraction cannot include a failure reason."
            )

        return self


class ExpectedBehavior(ContractModel):
    """
    Verified expectation created by application code.

    The ID is assigned only after the evidence quote has been
    verified against the original source.
    """

    id: str = Field(pattern=r"^EXP-\d{3}$")
    description: NonEmptyText
    category: ExpectationCategory
    evidence_quote: NonEmptyText


class ExpectationExtractionResult(ContractModel):
    """
    Trusted result returned by extract_expectations().

    It represents either:

    1. one or more verified expectations; or
    2. an explicit inability to validate, including a reason.
    """

    expectations: list[ExpectedBehavior] = Field(default_factory=list)
    cannot_validate: bool = False
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ExpectationExtractionResult:
        if self.cannot_validate:
            if self.expectations:
                raise ValueError(
                    "A cannot-validate result cannot carry expectations."
                )

            if self.reason is None:
                raise ValueError(
                    "A cannot-validate result must include a reason."
                )

            return self

        if not self.expectations:
            raise ValueError(
                "A successful extraction result must contain "
                "at least one verified expectation."
            )

        if self.reason is not None:
            raise ValueError(
                "A successful extraction result cannot include "
                "a failure reason."
            )

        return self