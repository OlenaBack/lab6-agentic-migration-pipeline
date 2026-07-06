# Foundry SDK Baseline

This folder contains the first Foundry-based version of the local migration-validation pipeline.

## How it works

`make_dataset.py` extracts grounded expectations from the source code and writes  the results to a .jsonl file,

`azure_llm_client.py` connects the project to a model deployed in Foundry through the **Responses API**.

`run_evaluation.py` passes the dataset to the **Azure AI Evaluation SDK**, which runs `FaithfulnessEvaluator` once per row and produces row-level results and metrics.

The returned judgments are then passed to `verdict.py` for the final deterministic decision.

```text
source + candidate
→ grounded expectations
→ dataset.jsonl
→ Azure AI Evaluation SDK
→ row-level evaluation
→ final decision
```

## Results in Foundry

When the run is linked to a Foundry project, the evaluation appears in the Foundry portal with row-level results and aggregated metrics. This makes it possible to inspect individual judgments, compare runs, and keep an evaluation history outside the local files.

## Main technologies

- Microsoft Foundry model deployment
- Foundry Responses API
- OpenAI Python SDK
- Azure AI Evaluation SDK
- Custom `FaithfulnessEvaluator`
- JSONL evaluation dataset

This track does not use Foundry prompt agents or the visual workflow.