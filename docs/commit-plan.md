# Commit plan

## Milestone: contextual dense retrieval, stage 1

- Status: implementation complete; paid pilot and full rollout pending approval.
- Scope: stable chunk IDs, page-delimited full-document context generation,
  resumable JSONL artifacts, a completeness manifest, and guarded indexing into
  `coating-compass-contextual-dense-v1`.
- Acceptance evidence: the offline dry run validates 36 source hashes and produces
  921 chunks; unit tests cover model-independent IDs, context bounds, stale prompt
  rejection, and preservation of original answer evidence.
- Rollout boundary: do not run Groq generation or OpenAI embedding calls without
  explicit owner approval. Review the 22010 TDS pilot before full-corpus generation.
- Suggested commit: `feat: add guarded contextual dense retrieval pipeline`
- Deferred: BM25, rank fusion, reranking, and comparative dashboards.

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
