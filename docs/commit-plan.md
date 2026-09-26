# Commit plan

## Milestone: Full-pipeline DeepEval baseline

- Status: implemented, executed, and organized for review.
- Scope: run the existing RAG graph over the golden set; score retrieval and
  generation together; add GEval simplicity and correctness rubrics; emit paired
  JSON and Markdown reports.
- Acceptance criteria:
  - The suite contains five standard RAG metrics and two named GEval metrics.
  - Golden inputs are validated before hosted calls begin.
  - JSON preserves metadata, answers, contexts, scores, reasons, and errors.
  - Markdown summarizes aggregate and per-case scores plus judge reasons.
  - Local unit tests do not make network or paid model calls.
- Suggested commit: `eval: add full-pipeline DeepEval metric suite`
- Deferred: selecting promotion thresholds and adding deterministic
  coating-safety metrics.

## Repository-layout cleanup

- Keep source and evaluation datasets under root `data/`.
- Keep application code under `src/app/`, dataset-generation code under `src/data/`,
  and evaluation code under `src/evals/`.
- Ignore raw PDFs, vector stores, result JSON, and transient tool state.
- Preserve the reviewed Markdown evaluation report as human-readable evidence.
- Suggested commit: `refactor: organize rag and evaluation modules`
