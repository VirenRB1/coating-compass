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

## Milestone: contextual BM25 retrieval

- Status: implemented locally; comparative evaluation pending.
- Scope: dependency-free tokenization and BM25 scoring over each validated generated
  context plus original manufacturer chunk.
- Evidence boundary: ranked results return the original chunk and citation metadata,
  never the synthetic context as manufacturer evidence.
- Acceptance criteria: deterministic ranking, retrieval through context or original
  text, empty results for unmatched terms, validation of parameters, and no hosted
  calls or generated index files.
- Suggested commit: `feat: add dependency-free contextual BM25 retrieval`
- Deferred: activating BM25 in the RAG application, reciprocal-rank fusion,
  reranking, stemming, and comparative hosted evaluation.
- Follow-up: added explicit `auto`, `baseline-dense`, `contextual-dense`, and
  `contextual-bm25` selection to application and evaluation entry points. No mode is
  promoted as the new default; `auto` preserves existing behavior.

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

## Milestone: framework-first simplification (2026-10-03)

- Status: verified; owner authorized the local commit.
- Owner requested repository-wide simplification and LangChain BM25 replacement.
- Scope: BM25Retriever plus evidence boundary, OpenAIEmbeddings, shared citation
  rendering, safe import/syntax cleanup, framework-first instructions and audit.
- Acceptance: original text/metadata preserved; zero-overlap queries return []; stale
  artifacts and v1 BM25 resumes fail; offline tests pass; paid evaluation remains separate.
- BM25 v2 rankings require fresh comparison with the reviewed cases before promotion.
- Suggested commit: `refactor: use LangChain retrieval and embeddings with original evidence`
- Include root AGENTS.md and decision files explicitly in the authorized commit;
  existing broad ignore rules remain unchanged.
