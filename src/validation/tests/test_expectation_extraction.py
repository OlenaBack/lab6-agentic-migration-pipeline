import json
from collections.abc import Callable

from validation.expectation_extraction import extract_expectations


GENERIC_SOURCE = """
def process(value):
    if value is None:
        raise ValueError("Value is required.")

    result = value * 2
    return result
""".strip()


def fake_llm(response: str) -> Callable[[str], str]:
    """Return an LLM callable that always returns the same response."""

    return lambda _prompt: response


def test_returns_grounded_expectations() -> None:
    llm_response = json.dumps(
        {
            "expectations": [
                {
                    "description": "A missing value raises an error.",
                    "category": "error",
                    "evidence_quote": (
                        'raise ValueError("Value is required.")'
                    ),
                },
                {
                    "description": "The value is multiplied by two.",
                    "category": "calculation",
                    "evidence_quote": "result = value * 2",
                },
            ],
            "cannot_validate": False,
            "reason": None,
        }
    )

    result = extract_expectations(
        source=GENERIC_SOURCE,
        llm_call=fake_llm(llm_response),
    )

    assert result.cannot_validate is False
    assert len(result.expectations) == 2

    assert {
        expectation.evidence_quote
        for expectation in result.expectations
    } == {
        'raise ValueError("Value is required.")',
        "result = value * 2",
    }


def test_empty_source_returns_cannot_validate() -> None:
    def llm_must_not_be_called(_prompt: str) -> str:
        raise AssertionError(
            "The LLM must not be called for an empty source."
        )

    result = extract_expectations(
        source="   \n\t",
        llm_call=llm_must_not_be_called,
    )

    assert result.cannot_validate is True
    assert result.expectations == []
    assert result.reason is not None


def test_rejects_ungrounded_expectation() -> None:
    llm_response = json.dumps(
        {
            "expectations": [
                {
                    "description": "The function writes to a database.",
                    "category": "side_effect",
                    "evidence_quote": "database.save(value)",
                }
            ],
            "cannot_validate": False,
            "reason": None,
        }
    )

    result = extract_expectations(
        source=GENERIC_SOURCE,
        llm_call=fake_llm(llm_response),
    )

    assert result.cannot_validate is True
    assert result.expectations == []
    assert result.reason is not None