# Evaluation plan

## Full-pipeline baseline

`src/evals/application_evals/evaluate_full_pipeline.py` runs every selected golden
question through both retrieval and generation before DeepEval scores the result.
It writes paired, timestamped JSON and Markdown artifacts under `reports/`.

The suite contains DeepEval's contextual recall, contextual precision, contextual
relevancy, answer relevancy, and faithfulness metrics. Two explicit GEval rubrics
add answer simplicity and answer correctness.

Answer simplicity rewards direct, understandable answers without rewarding unsafe
brevity. Necessary limitations, warnings, conditions, and citations do not count as
unnecessary complexity.

Answer correctness compares the generated answer with both the expected answer and
retrieved manufacturer evidence. It allows supported alternatives and different
wording, while penalizing contradictions, unsupported uses, wrong preparation or
primer decisions, missing qualifications, and unsafe advice.

These are LLM-as-judge measurements, not deterministic proof of coating safety.
Judge reasons must be reviewed, and later coating-specific validation should cover
SKU validity, citations, warnings, clarifications, compatible systems, and expected
abstention.

## Reproduction

The evaluation makes hosted model calls and may spend paid API credits. Obtain owner
approval before running it.

Metrics run sequentially within each case so every metric receives its own deadline.
Cases run in a bounded thread pool, defaulting to four concurrent cases. Completed
cases are checkpointed into the JSON artifact as they finish, and failed cases are
recorded without cancelling other in-flight work. The default per-metric timeout is
300 seconds and can be changed with `--metric-timeout-seconds`.

Provider 429 rate limits are retried with bounded backoff. Empty generator answers
are retained as baseline failures: retrieval metrics still run, while answer-level
metrics receive an explicit zero with `empty_actual_output`. This avoids hiding an
unreliable generator by repeatedly sampling until it returns an answer.

An incomplete artifact can be resumed with `--resume <json-path>`. Completed case
IDs are skipped, the dataset hash and label are checked, and only failed or missing
cases incur new model calls.

```powershell
uv run python -m src.evals.application_evals.evaluate_full_pipeline --label baseline
```

Use `--limit 1` only for an approved smoke run. The output records the golden-set
hash, model names, collection, retrieval count, label, timestamp, per-case scores,
judge reasons, generated answers, and retrieved evidence.

For example, the full baseline with four workers is:

```powershell
uv run python -m src.evals.application_evals.evaluate_full_pipeline --label baseline --workers 4 --metric-timeout-seconds 300
```
