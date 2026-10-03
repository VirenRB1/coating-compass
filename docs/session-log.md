# Session log

## 2026-09-27

- Added a dependency-free contextual BM25 retriever over the existing validated
  generated-context-plus-original-text records. It returns only original
  manufacturer chunks, makes no hosted calls, writes no index files, and is not yet
  activated in the application so it can be evaluated as one experimental variable.
- Kept the BM25 module itself entirely within Python's standard library by treating
  application documents as generic payloads.
- Made equal-score ranking deterministic by retaining and sorting on stable chunk ID
  instead of relying on corpus insertion order.
- Added explicit regression coverage that BM25 results preserve the stable chunk ID,
  source hash, filename, page number, and citation URL metadata unchanged.
- Added shared explicit retrieval selection to the interactive application and all
  evaluation entry points: `auto`, `baseline-dense`, `contextual-dense`, and
  `contextual-bm25`. `auto` retains the prior activation behavior, while evaluation
  artifacts record the resolved architecture and reject incompatible resumes.
- Corrected evaluation metadata so contextual BM25 records retrieval K and its
  `k1=1.5`, `b=0.75` settings but a null Qdrant collection; dense modes retain their
  real collection names.
- Simplified the increment for teaching: removed BM25 generics and its pass-through
  factory, eliminated repeated mode resolution in evaluators, and documented the
  shared `invoke(question)` interface used by local BM25 and LangChain Qdrant.
- Added focused tests for context-only discovery, original-text discovery, unmatched
  queries, record-shape integration, tokenization, and invalid configuration.
- Direct `uv run pytest` could not import `src`; verification uses
  `uv run python -m pytest`. Ruff is not installed in the current environment and no
  dependency was added solely for linting.

- Added an explicit OpenAI answer-generator option after the full contextual run hit
  Groq's 200,000-token daily limit. Provider and model are now recorded and protected
  on resume, preventing the nine completed GPT-OSS cases from being mixed silently
  with GPT-5 mini cases. The incomplete Groq artifact remains unchanged.
- Completed a fresh 20-case contextual-dense run with GPT-5 mini as generator and
  judge. The reviewed Markdown report records recall 0.596, precision 0.947,
  relevancy 0.630, answer relevancy 0.908, faithfulness 0.942, simplicity 0.870,
  and correctness 0.795. The machine-readable JSON remains an ignored local artifact.

- Extended the existing full-pipeline evaluator with `--goldens PATH` instead of
  adding a second orchestration path. The default remains the reviewed manual dataset.
- Strengthened local validation for non-empty questions, expected answers, context
  lists, and context passages; validation and resume hash/label checks now happen
  before any hosted prompt, embedding, generation, or judge setup.
- Recorded the golden path and SHA-256 in run metadata and exposed the path in the
  Markdown report. An omitted run label now uses the active Qdrant collection name.
- Added standard-library coverage for custom/default paths, malformed input, exact
  file hashing, and changed-input resume rejection. No hosted smoke run was performed.

- Built the separate local Qdrant collection
  `coating-compass-contextual-dense-v1` from all 921 validated contextual records,
  using `text-embedding-3-small` vectors with 1,536 dimensions and cosine distance.
  The existing `coating-compass-baseline-v1` collection remains intact with its own
  921 points.
- Verified a stored contextual point retains original manufacturer text as
  `page_content`; generated context is present only in metadata and carries the
  `generated_context_is_synthetic` marker. The vector input was generated context
  plus original text.
- All nine deterministic tests passed before ingestion. Ruff was unavailable in the
  current project environment, so lint was not run and no dependency was added merely
  to perform this ingestion step. Optional `fontTools` PDF warnings remained
  non-fatal.
- Completed the post-generation deterministic audit of
  `data/processed/contextual_dense_v1/chunks.jsonl`. All 921 records have unique,
  reproducible chunk IDs and exactly match the current 36 source PDFs, including
  document hashes, filenames, URLs, pages, offsets, original text, and text hashes.
  The complete manifest reports 921 successes and zero unresolved chunks.
- Reviewed one representative middle chunk from each of the 36 PDFs, plus the
  shortest and longest contexts and provider-boundary samples. The reviewed
  contexts were relevant and grounded in their original chunks. A normalized
  corpus-wide numeric check found no generated number absent from the associated
  source text.
- Recorded two non-blocking quality limitations: product SKU appears explicitly in
  638 of 921 contexts (69.3%), with most omissions in SDS records, and one legacy
  Groq context appears to describe SDS section 7 as page 7. Generated context is
  retrieval metadata only; original manufacturer text remains the answer evidence.
- Accepted the artifact for the contextual-dense retrieval experiment, while not
  treating this sample review as proof that every generated sentence is perfect.
  Measure targeted `manual_002` retrieval before deciding whether a version-2
  prompt and full regeneration are worthwhile.

## 2026-09-26

- Implemented the offline and guarded code path for contextual dense retrieval.
  Centralized deterministic PDF extraction/chunking, made chunk IDs independent of
  embedding models, added resumable per-document JSONL records and a corpus
  manifest, and preserved original manufacturer text as Qdrant page content.
- The no-network dry run validated all source hashes and reproduced 36 documents and
  921 chunks. It made no artifact writes and no hosted API calls.
- Added an automatic application/evaluation activation gate: the existing baseline
  stays active until the manifest is complete, then
  `coating-compass-contextual-dense-v1` is selected only after full record
  validation. The existing baseline Qdrant collection remains intact.
- Did not run the paid 22010 pilot, full contextualization, embedding, or evaluation.
  Those steps require explicit owner approval and pilot review.
- Simplified the implementation after a readability review: restored the original
  baseline `chunk_id` meaning, used the explicitly named `stable_chunk_id` only for
  contextual artifacts, and removed duplicated contextual-record setup from tests.
- The first 22010 pilot completed 3 of 10 chunks and recorded seven Groq TPM rate
  limits. Fixed retry timing to honor the provider's requested wait and corrected
  pilot completion reporting so `--document` checks the selected document rather
  than requiring all 921 corpus chunks.
- The resumed pilot reached 8 of 10 chunks. One remaining failure was another final
  TPM limit and one was a deterministic 114-token response. Increased the bounded
  attempt limit from three to five, added the measured length as retry feedback, and
  replaced partial-run tracebacks with a concise resumable CLI message.
- Relaxed the context acceptance ceiling from 100 to 120 approximate tokens while
  retaining the 50-100 prompt target. Raised the structured-output completion budget
  from 180 to 300 tokens after the final pilot chunk exhausted the smaller budget
  before Groq could produce valid JSON.
- While full-corpus contextualization ran, added deterministic `--case-id` selection
  to the retriever evaluator. This prepares a targeted `manual_002` check without
  spending hosted evaluation calls on the other 19 cases.
- The first full-corpus attempt reached Groq's 200,000-token daily quota after 40
  successful chunks and left retryable failure records. Changed daily-quota handling
  to stop immediately after checkpointing the current failure instead of repeating
  the same provider-wide error across later chunks.
- Added an explicit `--provider openai` continuation using `gpt-5-mini`. Contexts
  generated by Groq and OpenAI remain valid together under the same prompt and chunk
  schema. OpenAI quota errors stop and checkpoint the run; a provider-side project
  budget remains necessary because accepted API calls do not identify whether their
  balance came from free credits or paid funds.
- Added `--provider auto`: Groq remains primary, individual requests above Groq's
  8,000-token tier limit use OpenAI, and exhaustion of Groq's daily quota switches
  the remaining run to OpenAI. OpenAI quota exhaustion remains a checkpointed stop.
  Added a reusable delayed-start PowerShell helper whose log stays under ignored
  processed data.
- Switched the continuation plan to OpenAI-only `gpt-5-mini`. Confirmed the prompt
  layout keeps stable instructions and the full PDF before the varying chunk for
  automatic prefix caching. Added a compact `chunks.jsonl` export on full completion
  so routine use does not expose superseded Groq failure history.

- Registered version 1 of `coating_compass_baseline_prompt` in Langfuse with the
  `baseline` label. Added a tested prompt-registry boundary that fetches that label,
  validates text content, and exposes prompt/version/config metadata without yet
  changing the RAG graph's runtime prompt.
- Activated the fetched prompt through explicit graph dependency injection. The
  interactive app and generator-aware evaluation commands now use Langfuse prompt
  text, while evaluation artifacts record and resume-check the exact version.
- Goal: add a reference-inspired full-pipeline DeepEval evaluation.
- Added a seven-metric suite under `src/evals/application_evals/`.
- Added GEval rubrics for answer simplicity and answer correctness.
- Added paired timestamped JSON and Markdown reporting under `reports/`.
- Added deterministic tests for metric construction, golden validation, and averages.
- Did not run the hosted-model evaluation because it may spend paid API credits.
- Preserved the existing uncommitted generator-evaluation files.
- Next step: review the GEval rubrics and approve a one-case paid smoke run if desired.

### Smoke-run follow-up

- The first one-case smoke run reused all 921 stored embeddings successfully.
- Optional `fontTools` warnings appeared during PDF extraction but did not stop ingestion.
- DeepEval timed out because all seven synchronous metrics shared one 180-second call.
- Changed evaluation to run and checkpoint one metric per DeepEval call so the suite's
  combined runtime is no longer constrained by a single per-attempt deadline.
- The completed smoke result scored recall 0.600, precision 1.000, relevancy 0.340,
  answer relevancy 1.000, faithfulness 1.000, simplicity 0.900, and correctness 0.700.
- Added bounded parallel evaluation across cases, using four workers and a configurable
  300-second per-metric timeout by default.
- The full run completed 13 cases. One case hit the Groq token-per-minute limit and six
  cases produced empty generator answers that DeepEval could not score.
- Added bounded retry/backoff for transient 429s, explicit zero answer-level metrics
  for empty outputs, and exact-artifact resume so completed cases are not rerun.
- An automated resume attempt exposed Windows console encoding failures on DeepEval's
  Unicode progress symbols. The runner now configures stdout/stderr as UTF-8.
- Resumed the saved artifact and completed all 20 cases. Final averages were contextual
  recall 0.634, contextual precision 0.962, contextual relevancy 0.650, answer
  relevancy 0.731, faithfulness 0.722, answer simplicity 0.445, and answer correctness
  0.450. Five cases returned empty generator answers and were retained as explicit
  answer-level failures. DeepEval emitted non-fatal temporary-run-file warnings under
  parallel execution; the project-owned JSON and Markdown reports completed normally.
- Reviewed the owner's repository reorganization. Restored immutable source documents
  and evaluation inputs to root `data/`, because moving them under an ignored
  `src/data/` would have deleted the tracked benchmark on commit. Kept executable
  dataset-generation code under `src/data/`, application code under `src/app/`, and
  evaluation code under `src/evals/`. Added working README commands and replaced the
  placeholder root entry point with the baseline application entry point.
- Diagnosed the empty GPT-OSS output for `manual_002` as an undersized 700-token
  completion budget combined with the provider's default medium reasoning effort.
  Added validated, environment-configurable settings that default to 2,000 tokens and
  low reasoning effort, recorded them in evaluation artifacts, and added targeted
  `--case-id` evaluation so the remaining 19 cases need not be rerun.
- Ran only `manual_002` under label `generator-output-fix`. The generator returned
  2,652 characters instead of an empty answer, confirming the output-budget fix.
  The case completed all seven metrics: recall 0.375, precision 0.888, contextual
  relevancy 0.625, answer relevancy 1.000, faithfulness 1.000, simplicity 0.900,
  and correctness 0.700. Retrieval still missed the intended X-PERT 22010 evidence,
  so product selection remains a separate retrieval problem rather than a generator
  availability failure.

## 2026-10-03 - Framework-first repository simplification

- Goal: owner requested LangChain BM25 replacement, original-only manufacturer
  evidence, repository-wide simplification, and a durable framework-first rule.
- Starting state: clean staged/unstaged diffs on master at dfda785. Inspected Git,
  source/config/tests, README, project brief (actual Compass filename), handoff,
  tracking notes, and existing contextual evidence decision before editing.
- Replaced handwritten BM25 scoring with BM25Retriever/rank-bm25 plus LangChain
  Runnable composition for lexical-overlap filtering and original Document output.
  Removed the embeddings HTTP adapter in favor of OpenAIEmbeddings; disabled token
  splitting to preserve literal inputs. Removed unused direct requests dependency.
- Consolidated original-only citation formatting across the graph and all eval paths.
  Versioned BM25 identity as v2 and blocked v1 resumes by implementation metadata.
  Applied safe Ruff import/syntax cleanup repository-wide; preserved strict JSON
  validation, quota routing, source checks, and checkpoint/error contracts.
- Updated AGENTS.md, README, project brief, handoff, learning log, commit plan,
  reference map, decision 0001, and new decision 0002 (repository-wide audit).
  Corrected stale brief path and obsolete local command examples in AGENTS.md.
- Verification: all 24 deterministic unittest tests passed; git diff --check passed.
  Source/contextual dry run validated 36 documents and 921 chunks (921 complete,
  zero unresolved), without writes. Offline real-corpus BM25 smoke returned five
  X-PERT 22010 TDS/SDS chunks with source hash/page/URL metadata; unknown query
  returned []. New graph test proves synthetic context is absent from evidence sent
  to the fake generator. Tests verify ID collision/stale artifact rejection and v1
  resume refusal. No hosted model calls, local model weights, or index rebuilds.
- Lint: safe fixes applied. Full Ruff check still reports seven pre-existing rules:
  four TRY004 preferences for validation exception types and three BLE001 findings
  at explicit failure checkpoint/report boundaries. No suppressions were added;
  changing exception contracts belongs in a separate reviewed increment.
- Environment: uv first hit cache permissions, then private TLS issuer rejection;
  approved escalated uv --system-certs installed/locked the requested dependencies.
  pypdf emitted existing optional-fontTools warnings; corpus inventory is unchanged.
- Files changed: application BM25/evidence/embeddings; evaluation evidence/resume
  paths and reporting; focused tests; pyproject.toml/uv.lock; documentation above;
  import-only cleanup in remaining source modules and main.py.
- Existing ignore rules exclude root AGENTS.md and decision files. Edits are saved
  locally and the framework rule is also in tracked project docs. No staging,
  commit, push, deployment, visibility change, or ignore-policy change performed.
- Next step: review this diff, then authorize a fresh targeted BM25-v2 comparison
  against the reviewed goldens. Scoring differs from v1; no quality gain claimed.
- Last verified commit remains dfda785; this increment is uncommitted.

### Commit verification and owner authorization

The owner authorized a local commit after reviewing the implementation summary.
Reran all 24 offline tests successfully; diff whitespace checks passed. Ruff still
reports the same seven pre-existing TRY004/BLE001 findings. Include the reviewed
AGENTS.md and both decision documents explicitly despite existing broad ignore
rules; no secrets, PDFs, generated data, or vector stores are included. The next
step remains a separately approved BM25-v2 retrieval-quality evaluation. No push.
