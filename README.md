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

The component and full-pipeline commands call hosted judge models and should only run
with cost approval:

```powershell
uv run python -m src.evals.component_evals.evaluate_retriever --label baseline
uv run python -m src.evals.component_evals.evaluate_generator --label baseline
uv run python -m src.evals.application_evals.evaluate_full_pipeline --label baseline --workers 2 --metric-timeout-seconds 300
```

The full-pipeline evaluation writes a resumable JSON artifact and a human-readable
Markdown report. JSON artifacts are local run data; the reviewed Markdown baseline
may be committed as experiment evidence.
