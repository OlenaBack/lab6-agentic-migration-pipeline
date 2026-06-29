from functools import lru_cache

from openai import OpenAI


DEFAULT_MODEL = "gpt-5-nano"
MAX_OUTPUT_TOKENS = 6000


@lru_cache(maxsize=4)
def _client(api_key: str) -> OpenAI:
    """Create and reuse an OpenAI client for the supplied API key."""

    if not api_key.strip():
        raise ValueError("API key cannot be empty.")

    return OpenAI(api_key=api_key)


def call_llm(
    prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Send a prompt to the LLM and return its text response."""

    if not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    response = _client(api_key).responses.create(
        model=model,
        input=prompt,
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    if response.status == "incomplete":
        reason = getattr(
            response.incomplete_details,
            "reason",
            "unknown",
        )

        if reason == "max_output_tokens":
            raise RuntimeError(
                "LLM output was truncated because the output-token "
                "budget was exhausted."
            )

        raise RuntimeError(
            f"LLM response was incomplete: {reason}."
        )

    if response.status != "completed":
        error = getattr(response, "error", None)
        error_message = getattr(
            error,
            "message",
            "unknown error",
        )

        raise RuntimeError(
            f"LLM request ended with status "
            f"'{response.status}': {error_message}"
        )

    output = response.output_text.strip()

    if not output:
        raise RuntimeError("The LLM returned an empty response.")

    return output