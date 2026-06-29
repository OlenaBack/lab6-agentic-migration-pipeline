from collections.abc import Callable

from pydantic import ValidationError

from extract_expectations.contracts import (
    ExpectationExtractionPayload,
    ExpectationExtractionResult,
    ExpectedBehavior,
)
from extract_expectations.prompt import build_prompt


MIN_QUOTE_LENGTH = 3
DEFAULT_MIGRATION_RULES = "No additional migration rules were provided."


def extract_expectations(
    source: str,
    llm_call: Callable[[str], str],
    migration_rules: str = "",
) -> ExpectationExtractionResult:
    """
    Extract and verify expected behavior from the source file.

    The LLM produces untrusted expectation drafts. Application code
    verifies their evidence quotes and converts surviving drafts into
    verified ExpectedBehavior objects with assigned IDs.
    """

    # 1. Reject an empty source before calling the LLM.
    if not source.strip():
        return ExpectationExtractionResult(
            cannot_validate=True,
            reason="The source file is empty.",
        )

    effective_rules = migration_rules.strip() or DEFAULT_MIGRATION_RULES

    # 2. Build the prompt.
    prompt = build_prompt(source, effective_rules)

    # 3. Call the LLM.
    try:
        response_text = llm_call(prompt)
    except Exception:
        return ExpectationExtractionResult(
            cannot_validate=True,
            reason="The LLM call failed.",
        )

    if not response_text or not response_text.strip():
        return ExpectationExtractionResult(
            cannot_validate=True,
            reason="The LLM returned an empty response.",
        )

    # 4. Parse the untrusted LLM payload.
    try:
        payload = ExpectationExtractionPayload.model_validate_json(
            response_text
        )
    except ValidationError:
        return ExpectationExtractionResult(
            cannot_validate=True,
            reason=(
                "The LLM response did not match the expected "
                "extraction schema."
            ),
        )

    # Preserve a valid explicit decline from the model.
    if payload.cannot_validate:
        return ExpectationExtractionResult(
            cannot_validate=True,
            reason=payload.reason,
        )

    # 5. Verify drafts against the real source.
    normalized_source = " ".join(source.split())
    verified_expectations: list[ExpectedBehavior] = []

    for draft in payload.expectations:
        normalized_description = " ".join(draft.description.split())
        normalized_quote = " ".join(draft.evidence_quote.split())

        # Reject evidence that is too short to be meaningful.
        if len(normalized_quote) < MIN_QUOTE_LENGTH:
            continue

        # Reject invented or incorrectly copied evidence.
        if normalized_quote not in normalized_source:
            continue

        expectation_number = len(verified_expectations) + 1

        verified_expectations.append(
            ExpectedBehavior(
                id=f"EXP-{expectation_number:03d}",
                description=normalized_description,
                category=draft.category,
                evidence_quote=normalized_quote,
            )
        )

    # 6. Never return an empty successful result.
    if not verified_expectations:
        return ExpectationExtractionResult(
            cannot_validate=True,
            reason=(
                "No trustworthy expectations could be verified "
                "against the source."
            ),
        )

    return ExpectationExtractionResult(
        expectations=verified_expectations,
    )
