"""
Client for the Foundry behavior-comparison-agent.

One call = one (expectation, candidate) judgment, returned as the repo's
ComparisonJudgment contract.

Fail-closed: any unusable response (non-JSON, schema violation, wrong
expectation_id echoed back) degrades to an UNCLEAR judgment instead of
raising, mirroring compare_candidate's behavior in /src. One bad row must
not kill the pipeline; the verdict gate routes UNCLEAR to human review.

Requires: az login; FOUNDRY_PROJECT_ENDPOINT;
optional COMPARISON_AGENT_VERSION (pins the agent version).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from compare_candidate.contracts import ComparisonJudgment, ComparisonStatus

AGENT_NAME = "behavior-comparison-agent"
AGENT_VERSION = os.environ.get("COMPARISON_AGENT_VERSION", "4").strip()


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
        return _degraded(f"agent call failed ({exc}).")

    try:
        payload = json.loads(raw_response)
        if not isinstance(payload, dict):
            return _degraded("comparison response was not a JSON object.")
        returned_id = payload.pop("expectation_id", None)
        if returned_id is not None and returned_id != expectation_id:
            return _degraded(
                f"agent answered for '{returned_id}' "
                f"instead of '{expectation_id}'."
            )
        return ComparisonJudgment.model_validate(payload)
    except Exception as exc:
        return _degraded(f"comparison response unusable ({exc}).")