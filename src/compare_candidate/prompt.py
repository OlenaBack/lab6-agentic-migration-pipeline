CANDIDATE_MARKER = "<|CANDIDATE|>"
EXPECTATION_DESCRIPTION_MARKER = "<|EXPECTATION_DESCRIPTION|>"
EXPECTATION_EVIDENCE_MARKER = "<|EXPECTATION_EVIDENCE|>"


CANDIDATE_COMPARISON_PROMPT = """
You compare a migrated code CANDIDATE against ONE expected behavior taken
from the original source.

Decide whether the candidate preserves this single behavior:

- preserved: the candidate clearly does the same thing.
- missing: the behavior is absent from the candidate.
- changed: the behavior is present but differs (different type, value,
  rounding, exception raised, return shape, ...).
- unclear: the candidate does not provide enough to decide.

Rules:
- Judge only this one expectation, not the whole file.
- For missing, changed, or unclear, when possible quote the exact candidate
  code that supports your judgment in evidence_from_candidate.
- If the behavior is preserved, evidence_from_candidate may be null.
- Do not approve or reject the migration. Judge only this behavior.

Respond only with valid JSON in this shape:

{
  "status": "preserved",
  "evidence_from_candidate": "exact quote from the candidate, or null",
  "rationale": "one or two sentences"
}

EXPECTED BEHAVIOR:
<|EXPECTATION_DESCRIPTION|>

SOURCE EVIDENCE FOR THIS BEHAVIOR:
<|EXPECTATION_EVIDENCE|>

MIGRATED CANDIDATE:
--- CANDIDATE START ---
<|CANDIDATE|>
--- CANDIDATE END ---
""".strip()


def build_prompt(description: str, evidence: str, candidate: str) -> str:
    for marker in (
        CANDIDATE_MARKER,
        EXPECTATION_DESCRIPTION_MARKER,
        EXPECTATION_EVIDENCE_MARKER,
    ):
        if marker not in CANDIDATE_COMPARISON_PROMPT:
            raise RuntimeError(
                "The comparison prompt is missing a substitution marker; "
                "the template and build code are out of sync."
            )
    return (
        CANDIDATE_COMPARISON_PROMPT
        .replace(EXPECTATION_DESCRIPTION_MARKER, description)
        .replace(EXPECTATION_EVIDENCE_MARKER, evidence)
        .replace(CANDIDATE_MARKER, candidate)
    )
