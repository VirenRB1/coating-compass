"""The six experiment records, kept separate from RAG and judging code."""

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

import mlflow
from dotenv import load_dotenv

from src.config import ROOT, config_snapshot
from src.config import path as config_path

# An explicit list prevents accidental uploads of credentials, PDFs, or stores.
CODE_FILES = (
    "pyproject.toml",
    "uv.lock",
    "src/config.py",
    "src/app/basic_rag.py",
    "src/app/evidence.py",
    "src/app/contextual_bm25.py",
    "src/app/reranking.py",
    "src/app/prompt_registry.py",
    "src/data/corpus.py",
    "src/data/contextualize_documents.py",
    "src/evals/application_evals/evaluate_full_pipeline.py",
    "src/evals/application_evals/metrics.py",
    "src/evals/application_evals/reporting.py",
    "src/evals/tracking.py",
)


def flatten_params(values: dict, prefix: str = "") -> dict[str, str]:
    """Use dotted names; encode lists/null deterministically without losing values."""
    flattened = {}
    for key, value in sorted(values.items()):
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(flatten_params(value, name))
        else:
            flattened[name] = (
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False)
            )
    return flattened


class ExperimentTracker:
    def log_goldens(self, filename: Path) -> None:
        # 2. Fixed golden dataset, in its original JSON representation.
        mlflow.log_artifact(str(filename), "golden_dataset")

    def log_prompt(self, prompt) -> None:
        # 6. The same fetched text that is passed to create_rag_graph.
        mlflow.log_text(prompt.text, "system_prompt/system_prompt.txt")
        mlflow.set_tags(
            {
                "prompt.name": prompt.name,
                "prompt.version": prompt.version,
                "prompt.label": prompt.label,
            }
        )

    def log_results(self, output: dict, json_path: Path) -> None:
        # 3. Existing report schema contains answers, references, contexts, reasons.
        mlflow.log_artifact(str(json_path), "evaluation_dataset")
        mlflow.set_tags({"evaluation.status": output["run"]["status"]})
        # 4. Only final averages are comparable metrics; retain partials in JSON.
        if output["run"]["status"] == "complete":
            mlflow.log_metrics(
                {
                    name.lower().replace(" ", "_"): score
                    for name, score in output["averages"].items()
                }
            )
            mlflow.log_artifact(str(json_path.with_suffix(".md")), "evaluation_dataset")


@contextmanager
def track_experiment(params_path: Path | None, label: str | None):
    """One invocation, one run. Exceptions leave the MLflow run FAILED."""
    load_dotenv(ROOT / ".env")
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
    mlflow.set_experiment("coating-compass")
    # Refuse implicit reuse/nesting: this command owns a whole experiment.
    if mlflow.active_run() is not None or os.getenv("MLFLOW_RUN_ID"):
        raise RuntimeError(
            "Evaluation needs its own MLflow run; clear the active run/MLFLOW_RUN_ID."
        )
    with mlflow.start_run(run_name=label, tags={"stage": "development"}) as run:
        print(f"MLflow run ID: {run.info.run_id}", flush=True)
        # 1. Original YAML plus the validated configuration actually used.
        snapshot = config_snapshot()
        mlflow.log_artifact(str(params_path or ROOT / "params.yaml"), "configuration")
        mlflow.log_dict(snapshot, "configuration/validated_params.json")
        mlflow.log_params(flatten_params(snapshot["params"]))
        mlflow.set_tag("params_sha256", snapshot["params_sha256"])
        # 5. Current source bytes capture uncommitted edits too; Git is optional.
        for filename in CODE_FILES:
            source = ROOT / filename
            mlflow.log_artifact(
                str(source),
                (Path("reproducibility") / Path(filename).parent).as_posix(),
            )
        for name in ("source_manifest", "contextual_manifest"):
            manifest = config_path(name)
            if manifest.is_file():
                mlflow.log_artifact(
                    str(manifest), f"reproducibility/knowledge_base/{name}"
                )
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            commit = None
        if commit is not None and commit.returncode == 0:
            mlflow.set_tag("git.commit", commit.stdout.strip())
        yield ExperimentTracker()
