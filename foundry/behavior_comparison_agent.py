"""
Client for the Foundry behavior-comparison-agent.

One call = one (expectation, candidate) judgment, returned as the repo's
ComparisonJudgment contract.

Fail-closed with one retry: any unusable response (call failure,
non-JSON, schema violation, wrong expectation_id echoed back) is retried
once — observed slips (e.g. the model answering for an invented ID in a
stateless call) are random, so a single retry resolves most of them.
A second consecutive failure degrades to an UNCLEAR judgment instead of
raising, mirroring compare_candidate's behavior in /src. An explicit
'unclear' from the judge is a legitimate judgment, not a failure, and is
never retried.

Requires: az login; FOUNDRY_PROJECT_ENDPOINT;
optional COMPARISON_AGENT_VERSION (pins the agent version).
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from compare_candidate.contracts import ComparisonJudgment, ComparisonStatus

AGENT_NAME = "behavior-comparison-agent"
AGENT_VERSION = os.environ.get("COMPARISON_AGENT_VERSION", "4").strip()
MAX_ATTEMPTS = 2  # one call + one retry on degradation


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is not set.")
    return OpenAI(
        base_url=endpoint.rstrip("/") + "/openai/v1",
        api_key=get_bearer_token_provider(
            DefaultAzureCredential(), "https://ai.azure.com/.default"
        ),
    )


def _degraded(reason: str) -> ComparisonJudgment:
    return ComparisonJudgment(
        status=ComparisonStatus.UNCLEAR,
        evidence_from_candidate=None,
        rationale=f"Degraded: {reason}",
    )


def _attempt(
    expectation_id: str,
    user_message: str,
) -> tuple[ComparisonJudgment | None, str]:
    """
    One invocation of the agent. Returns (judgment, "") on success or
    (None, reason) when the response is unusable and a retry is
    warranted.
    """
    try:
        response = _client().responses.create(
            input=user_message,
            extra_body={
                "agent_reference": {
                    "type": "agent_reference",
                    "name": AGENT_NAME,
                    "version": AGENT_VERSION,
                },
            },
        )
        raw_response = response.output_text.strip()
    except Exception as exc:  # network, auth, agent errors
        return None, f"agent call failed ({exc})"

    try:
        payload = json.loads(raw_response)
    except ValueError:
        return None, "comparison response was not valid JSON"

    if not isinstance(payload, dict):
        return None, "comparison response was not a JSON object"

    returned_id = payload.pop("expectation_id", None)
    if returned_id is not None and returned_id != expectation_id:
        return None, (
            f"agent answered for '{returned_id}' "
            f"instead of '{expectation_id}'"
        )

    try:
        return ComparisonJudgment.model_validate(payload), ""
    except Exception as exc:
        return None, f"comparison response violated the contract ({exc})"


def compare_behavior(
    expectation_id: str,
    description: str,
    evidence_quote: str,
    candidate: str,
) -> ComparisonJudgment:
    """Compare one expected behavior with the migrated candidate."""

    user_message = (
        f"EXPECTATION ID:\n{expectation_id}\n\n"
        f"EXPECTED BEHAVIOR:\n{description}\n\n"
        f"SOURCE EVIDENCE:\n{evidence_quote}\n\n"
        "MIGRATED CANDIDATE:\n"
        "--- CANDIDATE START ---\n"
        f"{candidate}\n"
        "--- CANDIDATE END ---"
    )

    reasons: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        judgment, reason = _attempt(expectation_id, user_message)
        if judgment is not None:
            if attempt > 1:
                print(
                    f"      retry rescued {expectation_id} "
                    f"(attempt 1: {reasons[0]})",
                    file=sys.stderr,
                )
            return judgment
        reasons.append(f"attempt {attempt}: {reason}")

    return _degraded("; ".join(reasons) + ".")