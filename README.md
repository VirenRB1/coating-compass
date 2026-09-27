# Coating Compass

Coating Compass is an evidence-based coating recommendation assistant that
translates plain-language project descriptions into technical requirements and
retrieves supporting guidance from manufacturer Technical Data Sheets (TDS) and
Safety Data Sheets (SDS).

This is an unofficial learning and portfolio project. It is not affiliated with,
endorsed by, or presented as an official application of Dulux, PPG, or any other
manufacturer. Recommendations are decision support and should be verified
against the cited manufacturer documentation.

## Repository layout

- `src/app/`: baseline RAG ingestion, retrieval, and answer generation.
- `src/data/`: golden-dataset generation utilities.
- `src/evals/component_evals/`: retriever-only and generator-only evaluations.
- `src/evals/application_evals/`: full-pipeline DeepEval suite and reporting.
- `data/`: local source corpus, tracked evaluation inputs, and ignored generated stores.
- `reports/`: reviewable evaluation reports; machine-readable run JSON is ignored.
- `docs/`: project context, learning notes, evaluation plan, and session handoff.

The structure adapts lessons from the reference LLMOps repository without copying its
source, prompts, datasets, or generated artifacts.

## Setup

```powershell
uv sync
```

Copy `.env.example` to `.env` and supply the hosted-provider credentials you intend
to use. Do not commit `.env`.

## Run the baseline

```powershell
uv run python main.py
```

The baseline uses hosted embeddings and generation. It may incur API usage.

## Evaluation commands

Deterministic tests:

```powershell
uv run python -m unittest discover -s tests -v
```

Validate golden-generation inputs without calling a model:

```powershell
uv run python -m src.data.generate_manual_goldens
```

The component and full-pipeline commands call hosted retrieval, generation, and judge
models and should only run with cost approval. The full-pipeline command validates
the reviewed golden dataset before making those calls:

```powershell
uv run python -m src.evals.component_evals.evaluate_retriever --label baseline
uv run python -m src.evals.component_evals.evaluate_generator --label baseline
uv run python -m src.evals.application_evals.evaluate_full_pipeline `
  --goldens data/evaluations/manual_golden_dataset.json `
  --workers 2 `
  --metric-timeout-seconds 300
```

After the contextual collection is complete and indexed, run only the known
`manual_002` retrieval miss before considering a full evaluation:

```powershell
uv run python -m src.evals.component_evals.evaluate_retriever `
  --label contextual-dense-v1 `
  --case-id manual_002
```

When `--label` is omitted, the full-pipeline run label is the active Qdrant collection
name. `--label` remains available for an explicit experiment label. The command writes
a combined, resumable JSON dataset and a human-readable Markdown report under
`reports/full_pipeline_<label>_<timestamp>.json` and `.md`. Each JSON case retains the
reviewed answer/context, retrieved manufacturer context, actual application answer,
and all seven metric results and reasons. JSON artifacts are local run data; the
reviewed Markdown report may be committed as experiment evidence.

Resume an interrupted run with the same golden file and saved JSON artifact:

```powershell
uv run python -m src.evals.application_evals.evaluate_full_pipeline `
  --goldens data/evaluations/manual_golden_dataset.json `
  --resume reports/full_pipeline_<label>_<timestamp>.json
```

The saved input path and SHA-256 make the run auditable. Resume fails before hosted
calls if the golden file contents changed or its run label no longer matches.
Generator provider and model are also resume-protected so one report cannot silently
combine answers from different systems. To evaluate with GPT-5 mini as both the
application generator and judge, set these session variables and start a new run:

```powershell
$env:COATING_COMPASS_GENERATOR_PROVIDER = "openai"
$env:COATING_COMPASS_GENERATOR_MODEL = "gpt-5-mini-2025-08-07"
uv run python -m src.evals.application_evals.evaluate_full_pipeline `
  --goldens data/evaluations/manual_golden_dataset.json `
  --workers 1 `
  --metric-timeout-seconds 300
```

## Contextual dense retrieval

The contextual pipeline creates a synthetic, chunk-specific retrieval prefix from
each complete PDF. The prefix is embedded with the original chunk, but only the
unchanged manufacturer chunk is returned to the answer model as evidence.

Validate source hashes and reproduce the expected corpus inventory without network
or API calls:

```powershell
uv run python -m src.data.contextualize_documents --dry-run
```

The expected result is 36 documents and 921 chunks. Generated records and their
manifest are checkpointed under the ignored `data/processed/contextual_dense_v1/`
directory. A partial or stale artifact cannot be indexed.

After explicit approval for paid Groq calls, run the X-PERT Waterborne Alkyd pilot:

```powershell
uv run python -m src.data.contextualize_documents `
  --document 06_Dulux_XPERT_Waterborne_Alkyd_22010_01_TDS.pdf `
  --confirm-paid-calls
```

Review every pilot record before omitting `--document` for the resumable full-corpus
run. Application and evaluation ingestion remain on the baseline until all 921
records are complete. They then activate `coating-compass-contextual-dense-v1` only
after validating every record. Building the new collection calls the configured
OpenAI embedding API; the existing baseline collection remains untouched.

If Groq's daily free-tier quota stops a resumable corpus run, the remaining chunks
can use `gpt-5-mini` through the existing OpenAI account:

```powershell
uv run python -m src.data.contextualize_documents `
  --provider openai `
  --confirm-paid-calls
```

Use `--provider auto` to start with Groq, route Groq-oversized documents through
OpenAI, and switch the remaining run to OpenAI after Groq's daily quota is exhausted.
OpenAI quota exhaustion still stops the checkpointed run.

Groq and OpenAI records may coexist in the same manifest. Configure an OpenAI
project-side budget or credit cap first: the local command stops on an explicit API
quota rejection, but cannot determine whether an accepted request used promotional
or paid account balance.

OpenAI prompt caching is automatic for eligible repeated prefixes. Context generation
groups chunks sequentially by PDF and places the stable instructions and complete
document before the varying chunk. After all 921 chunks complete, the command writes
`data/processed/contextual_dense_v1/chunks.jsonl` with exactly one latest successful
record per chunk; append-only per-document records remain available for auditing.

Build or resume the separate contextual Qdrant collection without starting the
interactive application:

```powershell
$env:COATING_COMPASS_INGEST_ONLY = "1"
uv run python main.py
```

The command validates the complete contextual artifact before changing Qdrant. It
embeds only missing stable chunk IDs, so rerunning it reuses all completed points.
The local vector-store files under `data/vector_store/` are generated artifacts and
must not be committed.
