# lab6-agentic-migration-pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/OlenaBack/lab6-agentic-migration-pipeline/blob/main/src/pipeline/migration_validation.ipynb)

Validates AI-generated code migrations between any source and target
environment (for example, Python to C#).

The focus is **validation**, not migration. Given a source and a candidate,
the pipeline extracts a source-grounded specification of the behavior that
must be preserved, then grades the candidate against it. It does not compile
or run the candidate — conclusions are static and evidence-grounded.

```
load source + candidate
  → extract_expectations   grounded rubric (the spec)
  → compare_candidate      findings: did behavior survive?
  → decide                 deterministic verdict, no LLM
  → ValidationVerdict       approve · regenerate · human_review
```

![Validation modes](validation_modes_diagram.svg)

## Principles

- **Grounded** — every claim cites a verbatim source quote; ungrounded ones are dropped.
- **Bounded** — the LLM judges; deterministic code decides the verdict.
- **Fail-closed** — declines rather than guesses on failure or ambiguity.
- **Honest** — `APPROVE` means "no blocking issue in the checks run", not "proven equivalent".

## Limits

No compilation, execution, or differential testing. Candidate-side evidence
is trusted, not yet verified. Numeric-type differences (e.g. float vs decimal)
may pass unless the comparison prompt is tuned for them.

## Status

Built end to end on one source/candidate pair. Planned: unsupported-behavior
check, correction loop, seeded-mutation harness.

## Structure

Each pipeline step is a self-contained vertical slice:

```
src/
├── core/                   shared primitives: ContractModel, NonEmptyText,
│                           call_llm, read_source_file
├── extract_expectations/   contracts · prompt · run · tests
├── compare_candidate/      contracts · prompt · run · tests
├── decide/                 contracts · run · tests
└── pipeline/
    └── migration_validation.ipynb
```

Every slice owns its Pydantic contracts, prompt template (with a `build_prompt`
function), logic, and tests. `core/` holds the base class and shared type
primitives used across slices.

## Azure AI Foundry replication

The `foundry/` slice reproduces the pipeline as an Azure AI Foundry
evaluation: the same extraction prompt builds the rubric, a custom
`azure-ai-evaluation` evaluator reuses the comparison prompt and the
`ComparisonJudgment` contract, and the deterministic `decide()` runs as a
post-processing gate over the per-row results — restoring the verdict that
Foundry's native aggregation (a mean pass rate) does not express.

```
foundry/
├── azure_llm_client.py       call_azure_llm: Foundry twin of core.llm_client
├── make_dataset.py           extraction -> one JSONL row per expectation
├── faithfulness_evaluator.py custom evaluator (LLM judges status only; fail-closed)
├── verdict.py                rows -> ValidationFindings -> decide()
├── run_evaluation.py         evaluate() + portal logging + verdict
└── dataset.jsonl             generated rubric for the payroll example
```

Requires a Foundry project with a deployed model and, in the environment:
`AZURE_OPENAI_ENDPOINT` (the `/openai/v1` endpoint), `AZURE_OPENAI_API_KEY`,
and `AZURE_OPENAI_DEPLOYMENT` (the deployment name). Then, from the repo
root, with `PYTHONPATH=src;foundry` (Windows) or `src:foundry` (Unix):

```
pip install azure-ai-evaluation azure-identity
python foundry/make_dataset.py       # extraction -> foundry/dataset.jsonl
python foundry/run_evaluation.py     # evaluation -> metrics, portal run, verdict
```

Portal logging authenticates via Entra ID (`az login`). Runs logged through
the SDK may not appear in the New Foundry evaluations list; open the run via
its `studio_url` (written into `evaluation_results.json`) or the classic
portal view.

## Setup

```
pip install -r requirements.txt   # Python 3.12+
```

There is no package install step, so set `PYTHONPATH` before running tests or
importing directly from the repo root:

```
# Unix / macOS
export PYTHONPATH=src

# Windows (PowerShell)
$env:PYTHONPATH = "src"

# Windows (cmd)
set PYTHONPATH=src
```

Then run tests with:

```
python -m pytest src/
```

Fresh checkout: every package directory needs `__init__.py`, and Pydantic
contract files must not use `from __future__ import annotations`.
