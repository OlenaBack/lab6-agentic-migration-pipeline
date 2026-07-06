# Foundry Hybrid Agent Pipeline

This folder contains the more complete Foundry-based replication of the migration-validation pipeline originally implemented as a Jupyter notebook.

## How it works

The pipeline uses two prompt agents created in Microsoft Foundry:

- `expectation-extractor`
- `behavior-comparison-agent`

`run_foundry_pipeline.py` performs the following steps:

1. Calls the extractor agent several times.  
   Multiple passes improve recall because extraction results can vary.

2. Verifies and merges expectations locally.  
   The existing project code checks source evidence, removes duplicates, and assigns stable IDs such as `EXP-001`.

3. Calls the comparison agent once per expectation.  
   Each result contains a status, rationale, and candidate evidence. An unusable response is retried once and then degraded to `unclear`.

4. Runs a Foundry cloud evaluation.  "faithfulness-label"
   The expectation dataset is uploaded to Foundry and evaluated by an independent label-model judge.

5. Reconciles the two judgments.  
   The comparison-agent result is authoritative. A genuine disagreement with the evaluation judge is downgraded to `unclear`.

6. Calculates the final verdict with deterministic project code.

```text
source + candidate
→ repeated Foundry extraction
→ local grounding, union, and stable IDs
→ Foundry comparison agent per expectation
→ Foundry cloud evaluation cross-check
→ approve | regenerate | human_review
```

## Foundry technologies

- Foundry prompt agents with structured outputs
- Foundry Responses API with `agent_reference`
- OpenAI Python SDK
- Microsoft Entra authentication
- Azure AI Projects SDK
- Foundry datasets and cloud evaluations
- Label-model evaluator
- Portal-visible evaluation runs and metrics

Python keeps control of grounding, deduplication, disagreement handling, and the final verdict.

## Files

```text
foundry/
├── verdict.py
└── hybrid_agent_pipeline/
    ├── run_foundry_pipeline.py
    ├── make_dataset_from_agent.py
    ├── behavior_comparison_agent.py
    └── README.md
```

- `run_foundry_pipeline.py` — orchestrates the complete pipeline.
- `make_dataset_from_agent.py` — calls the extractor agent and can also generate an evaluation dataset separately.
- `behavior_comparison_agent.py` — calls the comparison agent and validates its structured response.
- `foundry/verdict.py` — shared deterministic verdict adapter.

## Prerequisites

The Foundry project must contain:

- `expectation-extractor`
- `behavior-comparison-agent`
- a deployed judge model

The signed-in account needs access to the Foundry project.

## Configuration

Required:

```powershell
$env:FOUNDRY_PROJECT_ENDPOINT = $env:FOUNDRY_PROJECT_ENDPOINT = "https://matrona-foundry.services.ai.azure.com/api/projects/legacy-code-migration-validation"
```

Optional:

```powershell
$env:EXTRACTOR_AGENT_VERSION = "3"
$env:COMPARISON_AGENT_VERSION = "4"
$env:EXTRACTION_PASSES = "3"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-5-nano"
$env:CANDIDATE_PATH = "path\to\candidate.cs"
```

## Results

Each run creates local artifacts such as:

```text
foundry/dataset_pipeline_<timestamp>.jsonl
foundry/pipeline_results_<timestamp>.json
```

The cloud evaluation is also available in Foundry with row-level judgments and aggregated metrics.

## Scope

This pipeline performs static, evidence-grounded validation. It does not compile or execute the source or candidate code.

The visual Foundry workflow is a separate proof of concept. This hybrid track keeps the complex validation logic in Python while using Foundry for agents, model inference, datasets, evaluations, and portal visibility.