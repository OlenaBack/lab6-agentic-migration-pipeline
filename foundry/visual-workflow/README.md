# Foundry Visual Workflow

This folder documents a low-code proof of concept built in the Microsoft Foundry visual workflow designer.

## Workflow overview

![Foundry visual workflow](workflow-overview.png)

## How it works

The workflow uses two Foundry agents:

- `expectation-extractor`
- `behavior-comparison-agent`

The extractor returns structured expectations. The workflow parses them, loops through each expectation, calls the comparison agent, updates counters, and calculates the final verdict with workflow expressions.

```text
input
→ extract expectations
→ parse structured output
→ compare each expectation
→ update counters
→ final decision
```

## Results in Foundry

Each workflow run is visible in Foundry with execution traces for every node and comparison-agent invocation.

The verdict rules are:

```text
all preserved        → approve
changed or missing   → regenerate
unclear or unusable  → human_review
```

## Main technologies

- Foundry visual workflow designer
- Foundry agents with structured outputs
- `ParseValue`
- `Foreach`
- workflow variables and Power Fx expressions
- `SendActivity`
- portal-visible execution traces

## Limitations

This proof of concept does not include repeated extraction, local evidence verification, deduplication, full result aggregation, or the independent evaluation cross-check used by the hybrid pipeline.

Each run should remain stateless so earlier conversation messages do not affect later validations.
