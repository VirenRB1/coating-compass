# Decision 0002: framework-first simplification

- Status: accepted; implementation verified offline, quality evaluation pending
- Date: 2026-10-03
- Authorization: owner requested BM25 replacement and repository-wide simplification.

## Problem and evidence

The repository implemented BM25 statistics/scoring and OpenAI embeddings HTTP calls
by hand despite already using LangChain and LangGraph. The working tree was clean
on `master` at `dfda785`; staged and unstaged diffs were inspected before editing.
LangChain's maintained BM25Retriever delegates to rank-bm25 BM25Okapi. Its default
top-K includes nonmatches and its scores can be zero or negative for matching terms.
Source: https://github.com/langchain-ai/langchain-community/blob/master/libs/community/langchain_community/retrievers/bm25.py

## Decision

Prefer maintained LangChain and LangGraph components wherever they satisfy safety
and evidence requirements. Retain custom coating validation, original-only evidence
boundaries, deterministic safety rules, and behavior unavailable in the framework.
Choose the least code the owner can clearly explain.

Build BM25 on synthetic context plus original text with BM25Retriever. Compose it
with LangChain Runnables that filter zero-overlap candidates and return the exact
original Document objects. Rank the full local corpus before filtering and taking K;
otherwise a zero-score nonmatch could displace a matching zero/negative-score chunk.
Normalize case and product-number punctuation. Validate unique IDs and parameters.
Sort input by stable ID for reproducible framework ties; no custom tie ranking.

Use OpenAIEmbeddings with `check_embedding_ctx_length=False`, 60-second timeout,
and two SDK retries. This preserves literal string embedding inputs and avoids
introducing local token splitting or a new tokenizer download. Shared citation
rendering serves application prompts and all evaluation paths.

## Repository-wide review

| Concern | Outcome and reason |
|---|---|
| BM25 statistics/scoring | Replaced by BM25Retriever/rank-bm25. |
| Embeddings HTTP adapter | Replaced by existing langchain-openai integration; removed direct requests dependency. |
| Dense retrieval, chat, splitting, graph | Already maintained framework components; retained. |
| Evidence rendering | Consolidated four implementations into one original-only helper. |
| Contextual Qdrant insertion | Retained: embeddings use synthetic prefix, stored page_content must remain original; normal add_documents couples both. |
| PDF extraction and source identity | Retained pypdf and deterministic hash/page/ID checks to avoid changing the corpus. |
| Context generation/checkpoints | Already uses structured output; keep quota-stop, provider routing, length feedback, and reproducible artifacts. Generic retries do not replace these semantics. |
| Golden generation | Retained strict JSON/schema checks and owner-selected source coverage. Generic partial JSON parsing can accept truncated responses; structured-output migration needs a separate reviewed increment. |
| DeepEval runners/reporting | Keep independent metric deadlines, explicit failures, input/model/prompt identity, and resumable reports. LangGraph checkpointing does not replace these experiment semantics. |
| Langfuse registry | Retained existing SDK and validated immutable-label snapshot. |
| Imports and simple syntax | Applied Ruff safe fixes across the repository. |

## Alternatives and trade-offs

Keeping handwritten BM25 avoids dependencies but duplicates maintained scoring.
Using bare BM25Retriever is smaller but exposes synthetic text and unrelated results.
The chosen composition adds only the evidence boundary. langchain-community adds
five resolved packages including rank-bm25; uv.lock records their versions.
Sorting all candidates adds work, acceptable for the current 921-chunk corpus;
revisit when measured latency or corpus size justifies a different maintained index.
Lexical overlap is necessary for this guard, not sufficient evidence of safe advice.

BM25Okapi differs from the prior positive-IDF formula. Retrieval identity is v2 and
`bm25_implementation=langchain-bm25okapi-v2` blocks resuming v1 BM25 evaluations.
Keep the same goldens, sources, chunks, prompts, and models when evaluating ranking.
No paid calls, embedding rebuild, model-weight download, push, or deployment
was performed. The owner subsequently authorized the local commit.

## Verification and debugging

Run `uv run python -m unittest discover -s tests -v`. Tests cover original text and
metadata, synthetic-context retrieval without prompt leakage, unknown queries,
filter-before-K for negative scores, duplicate IDs, stale artifact rejection, and
evaluation identity. Run `uv run python -m src.data.contextualize_documents --dry-run`
to validate source hashes/counts without writes or hosted calls.

If imports fail, run `uv sync`; on this Windows network `uv --system-certs sync`
uses the trusted issuer without disabling certificate verification. Empty BM25
results mean no query-term overlap; inspect tokenization and validated records.
Changed ranking requires a fresh v2 evaluation, not a v1 report resume.
