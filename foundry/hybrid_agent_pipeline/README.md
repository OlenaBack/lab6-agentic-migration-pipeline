# Foundry Hybrid Agent Pipeline

This folder contains the more complete Foundry-based version of the migration-validation pipeline.

## How it works

The pipeline uses two prompt agents created in Foundry:

- `expectation-extractor`
- `behavior-comparison-agent`

`run_foundry_pipeline.py` calls the extractor several times, verifies and merges grounded expectations locally, and assigns stable IDs.

Each expectation is then evaluated by the comparison agent. The resulting status, rationale, and candidate evidence are used as the main judgment.

The pipeline also uploads the dataset to Foundry and creates a cloud evaluation with the `faithfulness-label` label-model evaluator. Its result is used as an independent cross-check. A genuine disagreement is downgraded to `unclear`.

The final decision is produced by the existing deterministic verdict logic.

```text
source + candidate
→ repeated Foundry extraction
→ local verification and expectation union
→ Foundry comparison agent per expectation
→ Foundry cloud evaluation cross-check
→ final decision
```

## Results Locally and in Foundry

The run prints the final verdict and writes local dataset and result files.

The cloud evaluation also appears in Foundry with row-level judgments and aggregated metrics.

## Main technologies

- Foundry prompt agents with structured outputs
- Foundry Responses API with `agent_reference`
- OpenAI Python SDK
- Microsoft Entra authentication
- Azure AI Projects SDK
- Foundry datasets and cloud evaluations
- Label-model evaluator

Python keeps control of grounding, deduplication, disagreement handling, and the final verdict.
