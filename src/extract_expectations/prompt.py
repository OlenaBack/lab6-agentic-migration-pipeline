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
- side-effect

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


def build_prompt(source: str, rules: str) -> str:
    if (
        SOURCE_MARKER not in EXPECTATION_EXTRACTION_PROMPT
        or RULES_MARKER not in EXPECTATION_EXTRACTION_PROMPT
    ):
        raise RuntimeError(
            "The expectation-extraction prompt is missing its substitution "
            "markers; the prompt template and build code are out of sync."
        )
    return (
        EXPECTATION_EXTRACTION_PROMPT
        .replace(RULES_MARKER, rules)
        .replace(SOURCE_MARKER, source)
    )
