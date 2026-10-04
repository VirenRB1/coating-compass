# Coating Compass

Coating Compass translates painting projects into technical requirements and retrieves
supporting manufacturer TDS/SDS evidence. This is an unofficial learning project,
unaffiliated with Dulux or PPG. Recommendations must be checked against the cited documents.

## Repository layout

- `params.yaml`: pipeline settings and experiment controls.
- `src/config.py`: Pydantic validation, normalized snapshots, and configuration hashes.
- `src/app/`: ingestion, retrieval, original-only evidence, and LangGraph application.
- `src/data/`: source extraction, contextualization, and golden generation.
- `src/evals/`: component evaluation, concurrent full-pipeline comparisons, and reporting.
- `data/`: source corpus, reviewed evaluation inputs, and ignored generated stores.
- `reports/`: reviewable Markdown results and ignored machine-readable JSON.
- `docs/`: local project, learning, and session notes; excluded from Git.

Reference-repository lessons are adapted without copying its source, prompts, or datasets.

## Setup and configuration

```powershell
uv sync
uv run python -m src.config
```

Copy `.env.example` to `.env` for provider credentials and Langfuse connection settings.
Model choices, paths, chunking, retrieval, retries, parallelism, thresholds, prompt
name/label, and case selection come only from `params.yaml`. Old `COATING_COMPASS_*`
environment overrides are no longer read. Never place credentials in YAML.

Every entry point accepts `--params path/to/experiment.yaml`; the default is the
repository's `params.yaml`. Relative YAML paths resolve against the repository root.
All fields are required. Unknown fields, invalid types, nonfinite numbers, invalid
ranges, and inconsistent bounds fail before clients or output artifacts are created.
Pydantic permits ordinary coercion, such as `"5"` to integer `5`. Chunk separators
retain their whitespace exactly. Edit YAML before starting a new process.

For a one-question smoke evaluation, set `evaluation.case_ids: [manual_002]` and
`evaluation.limit: null`. Restore `case_ids: []` for all cases. Alternatively use
`limit` for the first N cases. Golden generation has its own `golden_generation.case_ids`.

Defaults preserve 1000/150 character chunks, hosted `text-embedding-3-small` embeddings
(1536 dimensions), Groq `openai/gpt-oss-20b` generation, GPT-5 mini judging, K=5,
and existing collection names. Groq is the provider; Grok is a different model family.
Prompt text, judge rubrics, and safety rules remain in their existing registry/code.

Changing embedding model, dimensions, distance, or chunking requires new collection
names. Qdrant metadata prevents incompatible index reuse; legacy baseline/contextual
v1 indexes are accepted only with their original configuration. Contextual artifact
versions, hashes, completeness, and original-text records are checked before indexing.

## Application and source inventory

These commands validate local inputs without API calls or writes:

```powershell
uv run python -m src.data.contextualize_documents --dry-run
uv run python -m src.data.generate_manual_goldens
```

The current corpus contains 36 documents and 921 chunks. Contextual records and their
manifest live under `paths.contextual_artifacts`; partial/stale artifacts cannot be
indexed. Adding `--generate` to golden generation acknowledges hosted costs.

After approving hosted model costs:

```powershell
uv run python main.py
uv run python main.py --ingest-only
```

Choose `retrieval.mode` in YAML: `auto`, `baseline-dense`, `contextual-dense`, or
`contextual-bm25`, or `contextual-hybrid`. Auto selects contextual dense when the manifest declares completion,
otherwise baseline dense. Explicit contextual modes fail on unusable artifacts.
Dense ingestion embeds missing chunks and reuses compatible existing points.

For a contextualization pilot, set `contextualization.document` to the PDF filename;
use `null` for the full corpus. Choose `contextualization.provider` as `groq`,
`openai`, or `auto`, then, with cost approval:

```powershell
uv run python -m src.data.contextualize_documents --confirm-paid-calls
```

Generation proceeds sequentially by PDF with append-only checkpoints. Auto routes
Groq-oversized requests to OpenAI and switches after Groq daily quota exhaustion;
OpenAI quota exhaustion stops the run. Provider records may coexist. Completion
writes one current successful record per chunk to `chunks.jsonl`.
`scripts/run_contextualization_after_delay.ps1` accepts operational `-StartAt` and
`-Params` arguments and reads its provider/artifact directory from YAML.

Inspect the configured Langfuse prompt with `uv run python -m src.app.prompt_registry`.
Register a new version with explicit approval using
`uv run python -m scripts.register_baseline_prompt`.

## Evaluation and reproducibility

These commands call hosted generator/judge models and require cost approval:

```powershell
uv run python -m src.evals.component_evals.evaluate_retriever --label baseline
uv run python -m src.evals.component_evals.evaluate_generator --label baseline
uv run python -m src.evals.application_evals.evaluate_full_pipeline --label experiment
uv run python -m src.evals.application_evals.evaluate_dense_comparison --label dense-comparison
```

`evaluation.comparison_modes` assigns baseline/contextual dense to A and B in order.
Questions and each answer's seven metrics run concurrently. `comparison_workers`
controls case workers; `generator_rpm` shares LangChain request pacing across both
modes. Three requests/minute is not an exact token limiter. Logs identify [A]/[B]
progress. Single-mode full-pipeline evaluation uses the same generator pacing.

Hybrid mode uses LangChain's `EnsembleRetriever` to fuse contextual dense and contextual
BM25 rankings with reciprocal rank fusion, deduplicated by stable chunk ID. Configure
`retrieval.hybrid_dense_k`, `hybrid_bm25_k`, `hybrid_weights` (dense, BM25), and
`hybrid_rrf_c` in YAML; `retrieval.k` limits the final evidence count. Initial controls
are 5 candidates per branch, equal weights, RRF constant 60, and 5 final original
manufacturer chunks. It reuses the contextual dense collection and builds BM25 in
memory; no additional persistent index is required. Reports record the fusion settings.
Use a separate complete YAML with `retrieval.mode: contextual-hybrid` to evaluate it
without changing the application's `auto` default.

### Cohere reranking experiment

Set `retrieval.mode: contextual-hybrid` and `reranking.enabled: true` in a complete
experiment YAML. The flow becomes contextual dense + BM25 -> RRF -> Cohere -> final
K original manufacturer passages. Cohere sees the full deduplicated candidate pool
(up to 10 with current settings), before the final five-passage cut. It receives only
original passage text, preserves citation metadata, and adds `relevance_score`.
This orders/selects passages; it does not summarize them or establish coating safety.
No relevance threshold is applied. Set `reranking.enabled: false` to compare RRF alone.

Create a **trial/evaluation** key at https://dashboard.cohere.com/api-keys and set
`COHERE_API_KEY` in your local `.env`. A production key can incur charges; the application
cannot identify the billing tier from the key. Cohere currently documents 1,000 trial
calls/month and 10 rerank requests/minute:
https://docs.cohere.com/v2/docs/rate-limits.
The selected model is `rerank-v4.0-fast`; configure its name, timeout, and shared pacing
under `reranking`. Nine requests/minute leaves headroom for the trial limit; the limiter
is shared by case workers within one retriever/process, not across separate terminals.
Automatic SDK retries are disabled so they cannot bypass pacing. API failures surface
and can be resumed; the pipeline does not silently fall back to unreranked evidence.

Prepared local configurations (ignored under `data/evaluations/results/`):

```powershell
# Offline configuration validation
uv run python -m src.config --params data/evaluations/results/params-cohere-smoke.yaml
# After approving hosted generator/judge costs
uv run python -m src.evals.application_evals.evaluate_full_pipeline `
  --params data/evaluations/results/params-cohere-smoke.yaml --label cohere-smoke
```

The smoke configuration selects `manual_002`; `params-cohere-full.yaml` selects all
20 cases. Both preserve the prior hybrid candidate counts, weights, final K, generator,
judge, prompt, and corpus. They change only reranking (plus operational worker/case
selection). Reports record the reranker identity and normalized settings; new fields
must be added to old YAML files before validation, without altering historical reports.
Cohere access was verified on `manual_002`: ten BM25-selected original passages were
reranked to five, with unchanged source text and citation metadata. This checked the
hosted API and evidence boundary without paid embeddings, generation, or judging;
it was not the full hybrid experiment. Full-pipeline evaluation remains pending.

Full-pipeline/comparison reports go under `paths.reports`; component JSON goes under
`paths.evaluation_results`. Cases preserve references, original manufacturer context,
answers, scores, and judge reasons. Each new run stores `run.params` (normalized
validated settings) and `run.params_sha256` (canonical SHA-256); Markdown displays
the hash. These prepare later MLflow logging. No MLflow server/uploads are enabled yet.

Resume with identical YAML, dataset, and experiment label:

```powershell
uv run python -m src.evals.application_evals.evaluate_full_pipeline `
  --label experiment --resume reports/full_pipeline_experiment_<timestamp>.json
uv run python -m src.evals.application_evals.evaluate_dense_comparison `
  --label dense-comparison `
  --resume-a reports/full_pipeline_dense-comparison-A_<timestamp>.json `
  --resume-b reports/full_pipeline_dense-comparison-B_<timestamp>.json
```

Resume rejects changed settings, dataset hashes, retrieval/generator identities, or
prompt versions. Historical reports without snapshots remain readable but cannot
be resumed; start a new run instead of inventing configuration for old evidence.
Full-pipeline and comparison checkpoints preserve answers and completed metrics.
When all pending answers are saved, resume skips retrieval/generation and runs only
missing metrics. Failed attempts remain recorded in run metadata. The generator
component automatically resumes matching partial runs.

## Framework-first engineering

Prefer maintained LangChain/LangGraph components wherever they satisfy safety and
evidence requirements. Keep explicit coating-specific validation, original-only
evidence boundaries, deterministic safety rules, and unsupported framework behavior.

Contextual dense embeddings and LangChain's `BM25Retriever` index synthetic context
plus original text; answer generation and judges receive only unchanged manufacturer
chunks and citations. BM25 is rebuilt in memory without network calls or index files.
Its Runnable boundary filters results without query-term overlap and restores
original Documents. Unknown/punctuation-only queries return no evidence; this guard
is not a relevance or safety guarantee. Matching BM25Okapi scores may be zero/negative.

BM25 identity is `coating-compass-contextual-bm25-v2`, with
`bm25_implementation=langchain-bm25okapi-v2`. Do not resume handwritten v1 runs.
BM25 records no embedding model or Qdrant collection. Hosted embeddings use LangChain
with automatic token splitting disabled to preserve input text. Immutable PDFs,
generated embeddings, vector stores, and secrets must never be committed publicly.

Automated test files were removed at the owner's request. Use offline validation
above and `uv --system-certs tool run ruff check .` for lint. Keep updating the ignored
local learning/configuration notes under `docs/`.
