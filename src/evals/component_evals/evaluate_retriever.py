import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import truststore
from deepeval import evaluate
from deepeval.evaluate import AsyncConfig, CacheConfig
from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase
from dotenv import load_dotenv

from src.app.basic_rag import (
    RETRIEVAL_K,
    RETRIEVAL_MODES,
    build_retriever,
    retrieval_metadata,
)
from src.app.evidence import render_retrieval_context

GOLDENS_PATH = Path("data/evaluations/manual_golden_dataset.json")
RESULTS_DIRECTORY = Path("data/evaluations/results")
REPORT_PATH = Path("data/evaluations/retriever_evaluation_report.md")
METRIC_NAMES = [
    "Contextual Recall",
    "Contextual Precision",
    "Contextual Relevancy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the baseline retriever.")
    parser.add_argument("--label", default="baseline")
    parser.add_argument(
        "--retrieval-mode", choices=RETRIEVAL_MODES, default="auto"
    )
    parser.add_argument(
        "--case-id",
        action="append",
        help="Evaluate only this manual_NNN case ID. Repeat to select more than one.",
    )
    return parser.parse_args()


def select_goldens(
    goldens: list[dict], case_ids: list[str] | None
) -> list[tuple[int, dict]]:
    indexed_goldens = list(enumerate(goldens, start=1))
    selected_ids = set(case_ids or [])
    if not selected_ids:
        return indexed_goldens

    selected = [
        (index, golden)
        for index, golden in indexed_goldens
        if f"manual_{index:03d}" in selected_ids
    ]
    found_ids = {f"manual_{index:03d}" for index, _ in selected}
    if missing_ids := selected_ids - found_ids:
        raise ValueError(f"Unknown case IDs: {sorted(missing_ids)}")
    return selected


def write_markdown_report() -> None:
    runs = []
    for path in RESULTS_DIRECTORY.glob("retriever_*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("run", {}).get("status") == "complete":
            runs.append(run)

    latest_by_label = {}
    for run in sorted(runs, key=lambda item: item["run"]["timestamp_utc"]):
        latest_by_label[run["run"]["label"]] = run

    lines = [
        "# Retriever Evaluation Results",
        "",
        "Generated from completed DeepEval result artifacts. Scores use a 0–1 scale.",
        "",
    ]
    for label, run in latest_by_label.items():
        metadata = run["run"]
        lines.extend(
            [
                f"## {label.title()} — {metadata['timestamp_utc']}",
                "",
                f"- Collection: `{metadata['collection']}`",
                f"- Retrieval K: `{metadata['retrieval_k']}`",
                f"- Embedding model: `{metadata['embedding_model']}`",
                f"- Evaluation model: `{metadata['evaluation_model']}`",
                f"- Golden dataset SHA-256: `{metadata['goldens_sha256']}`",
                "",
                "| Metric | Average | Passed |",
                "|---|---:|---:|",
            ]
        )
        for name in METRIC_NAMES:
            passed = sum(case["metrics"][name]["success"] for case in run["cases"])
            lines.append(
                f"| {name} | {run['averages'][name]:.3f} | "
                f"{passed}/{len(run['cases'])} |"
            )
        lines.extend(
            [
                "",
                "| Case | Recall | Precision | Relevancy |",
                "|---|---:|---:|---:|",
            ]
        )
        for case in run["cases"]:
            lines.append(
                f"| {case['case_id']} | "
                f"{case['metrics']['Contextual Recall']['score']:.3f} | "
                f"{case['metrics']['Contextual Precision']['score']:.3f} | "
                f"{case['metrics']['Contextual Relevancy']['score']:.3f} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Architecture Comparison",
            "",
            "| Architecture | Recall | Precision | Relevancy | Cases |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, run in latest_by_label.items():
        lines.append(
            f"| {label} | {run['averages']['Contextual Recall']:.3f} | "
            f"{run['averages']['Contextual Precision']:.3f} | "
            f"{run['averages']['Contextual Relevancy']:.3f} | "
            f"{len(run['cases'])} |"
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    truststore.inject_into_ssl()
    load_dotenv()
    goldens = json.loads(GOLDENS_PATH.read_text(encoding="utf-8"))
    indexed_goldens = select_goldens(goldens, args.case_id)
    retriever = build_retriever(args.retrieval_mode)
    retrieval_config = retrieval_metadata(args.retrieval_mode)

    test_cases = []
    for index, golden in indexed_goldens:
        documents = retriever.invoke(golden["question"])
        retrieval_context = render_retrieval_context(documents)
        test_cases.append(
            LLMTestCase(
                input=golden["question"],
                actual_output="Retriever-only evaluation",
                expected_output=golden["expected_answer"],
                retrieval_context=retrieval_context,
                name=f"manual_{index:03d}",
            )
        )

    model = os.getenv("COATING_COMPASS_EVALUATION_MODEL", "gpt-5-mini-2025-08-07")
    metrics = [
        ContextualRecallMetric(model=model, async_mode=False),
        ContextualPrecisionMetric(model=model, async_mode=False),
        ContextualRelevancyMetric(model=model, async_mode=False),
    ]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIRECTORY / f"retriever_{args.label}_{timestamp}.json"
    output = {
        "run": {
            "label": args.label,
            "timestamp_utc": timestamp,
            "status": "running",
            **retrieval_config,
            "embedding_model": (
                None
                if retrieval_config["retrieval_mode"] == "contextual-bm25"
                else os.getenv(
                    "COATING_COMPASS_EMBEDDING_MODEL", "text-embedding-3-small"
                )
            ),
            "evaluation_model": model,
            "goldens_sha256": hashlib.sha256(GOLDENS_PATH.read_bytes()).hexdigest(),
            "case_ids": [f"manual_{index:03d}" for index, _ in indexed_goldens],
        },
        "averages": {},
        "cases": [],
    }

    for index, test_case in enumerate(test_cases, start=1):
        result = evaluate(
            test_cases=[test_case],
            metrics=metrics,
            hyperparameters={
                "architecture": args.label,
                "embedding_model": output["run"]["embedding_model"],
                "evaluation_model": model,
                "retrieval_k": RETRIEVAL_K,
            },
            async_config=AsyncConfig(run_async=False),
            cache_config=CacheConfig(write_cache=True, use_cache=True),
        )
        test_result = result.test_results[0]
        metric_results = {
            metric.name: {
                "score": metric.score,
                "threshold": metric.threshold,
                "success": metric.success,
                "reason": metric.reason,
                "error": metric.error,
            }
            for metric in (test_result.metrics_data or [])
        }
        output["cases"].append(
            {
                "case_id": test_result.name,
                "question": test_result.input,
                "retrieval_context": test_result.retrieval_context,
                "metrics": metric_results,
            }
        )
        metric_names = [metric.__name__ for metric in metrics]
        output["averages"] = {
            name: sum(case["metrics"][name]["score"] for case in output["cases"])
            / len(output["cases"])
            for name in metric_names
        }
        output_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Saved case {index}/{len(test_cases)} to {output_path}")

    output["run"]["status"] = "complete"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_markdown_report()
    print("\nCombined results for all cases:")
    for name, average in output["averages"].items():
        passed = sum(case["metrics"][name]["success"] for case in output["cases"])
        print(
            f"- {name}: average={average:.3f}, "
            f"passed={passed}/{len(output['cases'])}"
        )
    print(f"Saved retriever evaluation results to {output_path}")


if __name__ == "__main__":
    main()
