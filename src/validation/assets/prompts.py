# Markers substituted by build code. Defined here, next to the template,
# so the prompt and the function can never disagree about their spelling.
SOURCE_MARKER = "<|SOURCE|>"
RULES_MARKER = "<|MIGRATION_RULES|>"


EXPECTATION_EXTRACTION_PROMPT = """
You extract explicit behavioral expectations from source code.

Each expectation must describe one behavior that a correct migration
must preserve.

Allowed categories:
- input
- calculation
- output
- error
- side_effect

Grounding rules:
- Every expectation must include an exact quote from SOURCE CODE.
- Differences in indentation or whitespace are acceptable.
- Do not invent, paraphrase, or reconstruct evidence.
- Do not use the migration rules as evidence.
- Do not infer behavior that the source does not establish.
- Do not generate expectation IDs.
- If no meaningful grounded expectations can be extracted, return
  cannot_validate=true with a reason.

Respond only with valid JSON using one of these two shapes.

Successful extraction:

{
  "expectations": [
    {
      "description": "What behavior must be preserved",
      "category": "input",
      "evidence_quote": "Exact quote copied from the source"
    }
  ],
  "cannot_validate": false,
  "reason": null
}

Unable to extract grounded expectations:

{
  "expectations": [],
  "cannot_validate": true,
  "reason": "Explain why grounded expectations cannot be extracted"
}

MIGRATION RULES:
<|MIGRATION_RULES|>

SOURCE CODE:
--- SOURCE START ---
<|SOURCE|>
--- SOURCE END ---
""".strip()

# Markers for the comparison prompt, defined next to the template.
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