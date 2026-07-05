"""
Azure OpenAI twin of core.llm_client.

Same Responses API contract as call_llm, but routed to the Foundry
deployment via Azure's OpenAI-compatible v1 endpoint. The model argument
is the *deployment name*, not the model family name.
"""

from __future__ import annotations

import os
from functools import lru_cache

from openai import OpenAI

MAX_OUTPUT_TOKENS = 6000

ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
API_KEY_ENV = "AZURE_OPENAI_API_KEY"
DEPLOYMENT_ENV = "AZURE_OPENAI_DEPLOYMENT"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set.")
    return value


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=_require(ENDPOINT_ENV),
        api_key=_require(API_KEY_ENV),
    )


def call_azure_llm(prompt: str) -> str:
    """Send a prompt to the Foundry deployment and return its text response."""

    if not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    response = _client().responses.create(
        model=_require(DEPLOYMENT_ENV),
        input=prompt,
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    if response.status == "incomplete":
        reason = getattr(response.incomplete_details, "reason", "unknown")
        raise RuntimeError(f"LLM response was incomplete: {reason}.")

    if response.status != "completed":
        error = getattr(response, "error", None)
        message = getattr(error, "message", "unknown error")
        raise RuntimeError(
            f"LLM request ended with status '{response.status}': {message}"
        )

    output = response.output_text.strip()
    if not output:
        raise RuntimeError("The LLM returned an empty response.")
    return output