# lab6-agentic-migration-pipeline

A Jupyter/Colab agentic pipeline for legacy-code migration, focused on
**validating** AI-generated intermediate and final artifacts.

The pipeline migrates a small Python program to C# two ways — directly from
the source, and from generated-then-validated documentation — then checks
both against a human-prepared reference. It does not compile or run the
migrated code; conclusions are limited to static and semantic validation.

## Status
Step 1 — source and reference preparation (in progress).
