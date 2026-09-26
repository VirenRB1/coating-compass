# Session log

## 2026-09-26

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
