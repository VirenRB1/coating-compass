import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import truststore
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from dotenv import load_dotenv

from src.app.basic_rag import (
    build_retriever,
    create_rag_graph,
    retrieval_metadata,
)
from src.app.evidence import render_retrieval_context
from src.app.prompt_registry import fetch_baseline_prompt
from src.config import (
    add_params_argument,
    config_snapshot,
    get_params,
    load_params,
    metric_threshold,
    select_cases,
    validate_resume_config,
)
from src.config import path as config_path

METRIC_NAMES = ["Answer Relevancy", "Faithfulness"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the configured component.")
    add_params_argument(parser)
    parser.add_argument("--label", help="Run label.")
    args = parser.parse_args()
    settings = load_params(args.params)
    args.label = args.label or settings.evaluation.component_label
    args.retrieval_mode, args.case_id = (
        settings.retrieval.mode,
        settings.evaluation.case_ids,
    )
    return args


def evaluate_case(test_case: LLMTestCase, judge_model: str) -> dict:
    if not (test_case.actual_output or "").strip():
        metric_results = {
            name: {
                "score": 0.0,
                "threshold": metric_threshold(name),
                "success": False,
                "reason": "The baseline generator returned an empty answer.",
                "error": "empty_actual_output",
            }
            for name in METRIC_NAMES
        }
    else:
        metric_results = {}
        for metric in (
            AnswerRelevancyMetric(
                model=judge_model,
                threshold=get_params().evaluation.thresholds.answer_relevancy,
                async_mode=False,
            ),
            FaithfulnessMetric(
                model=judge_model,
                threshold=get_params().evaluation.thresholds.faithfulness,
                async_mode=False,
            ),
        ):
            metric.measure(test_case)
            metric_results[metric.__name__] = {
                "score": metric.score,
                "threshold": metric.threshold,
                "success": metric.success,
                "reason": metric.reason,
                "error": metric.error,
            }

    return {
        "case_id": test_case.name,
        "question": test_case.input,
        "actual_answer": test_case.actual_output,
        "retrieval_context": test_case.retrieval_context,
        "metrics": metric_results,
    }


def write_markdown_report() -> None:
    runs = []
    for path in config_path("evaluation_results").glob("generator_*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("run", {}).get("status") == "complete":
            runs.append(run)

    latest_by_label = {}
    for run in sorted(runs, key=lambda item: item["run"]["timestamp_utc"]):
        latest_by_label[run["run"]["label"]] = run

    lines = [
        "# Generator Evaluation Results",
        "",
        "Generated from completed DeepEval result artifacts. Scores use a 0-1 scale.",
        "",
    ]
    for label, run in latest_by_label.items():
        metadata = run["run"]
        lines.extend(
            [
                f"## {label.title()} - {metadata['timestamp_utc']}",
                "",
                f"- Collection: `{metadata['collection']}`",
                f"- Retrieval K: `{metadata['retrieval_k']}`",
                f"- Generator model: `{metadata['generator_model']}`",
                f"- Judge model: `{metadata['evaluation_model']}`",
                f"- Golden dataset SHA-256: `{metadata['goldens_sha256']}`",
                f"- Parameters SHA-256: `{metadata.get('params_sha256', 'not recorded (historical run)')}`",
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
                "| Case | Answer Relevancy | Faithfulness |",
                "|---|---:|---:|",
            ]
        )
        for case in run["cases"]:
            lines.append(
                f"| {case['case_id']} | "
                f"{case['metrics']['Answer Relevancy']['score']:.3f} | "
                f"{case['metrics']['Faithfulness']['score']:.3f} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Architecture Comparison",
            "",
            "| Architecture | Answer Relevancy | Faithfulness | Cases |",
            "|---|---:|---:|---:|",
        ]
    )
    for label, run in latest_by_label.items():
        lines.append(
            f"| {label} | {run['averages']['Answer Relevancy']:.3f} | "
            f"{run['averages']['Faithfulness']:.3f} | {len(run['cases'])} |"
        )
    config_path("generator_report").parent.mkdir(parents=True, exist_ok=True)
    config_path("generator_report").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    truststore.inject_into_ssl()
    load_dotenv()
    goldens = json.loads(config_path("goldens").read_text(encoding="utf-8"))
    goldens_hash = hashlib.sha256(config_path("goldens").read_bytes()).hexdigest()
    indexed_goldens = select_cases(goldens)
    partial_runs = []
    for path in config_path("evaluation_results").glob(
        f"generator_{args.label}_*.json"
    ):
        candidate = json.loads(path.read_text(encoding="utf-8"))
        run = candidate.get("run", {})
        if run.get("status") == "running" and run.get("goldens_sha256") == goldens_hash:
            partial_runs.append((path, candidate))

    for _, candidate in partial_runs:
        validate_resume_config(candidate["run"])
    prompt_version = fetch_baseline_prompt()
    retrieval_config = retrieval_metadata(args.retrieval_mode)
    judge_model = get_params().evaluation.generator_judge_model
    generator_model = get_params().generator.model
    config_path("evaluation_results").mkdir(parents=True, exist_ok=True)
    if partial_runs:
        output_path, output = max(
            partial_runs, key=lambda item: item[1]["run"]["timestamp_utc"]
        )
        validate_resume_config(output["run"])
        saved_prompt_version = output["run"].get("prompt_version")
        if (
            saved_prompt_version is not None
            and saved_prompt_version != prompt_version.version
        ):
            raise ValueError("Cannot resume: Langfuse prompt version has changed.")
        if output["run"].get("collection") != retrieval_config["collection"]:
            raise ValueError("Cannot resume: retrieval mode has changed.")
        if (
            output["run"].get("bm25_implementation")
            != retrieval_config["bm25_implementation"]
        ):
            raise ValueError("Cannot resume: BM25 implementation has changed.")
        print(
            f"Resuming {len(output['cases'])}/{len(indexed_goldens)} cases from {output_path}"
        )
    else:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output_path = (
            config_path("evaluation_results")
            / f"generator_{args.label}_{timestamp}.json"
        )
        output = {
            "run": {
                **config_snapshot(),
                "label": args.label,
                "timestamp_utc": timestamp,
                "status": "running",
                "prompt_name": prompt_version.name,
                "prompt_label": prompt_version.label,
                "prompt_version": prompt_version.version,
                **retrieval_config,
                "generator_provider": get_params().generator.provider,
                "generator_model": generator_model,
                "evaluation_model": judge_model,
                "goldens_sha256": goldens_hash,
            },
            "averages": {},
            "cases": [],
        }

    rag_graph = create_rag_graph(
        build_retriever(args.retrieval_mode), prompt_version.text
    )
    completed_ids = {case["case_id"] for case in output["cases"]}
    pending = []
    for index, golden in indexed_goldens:
        case_id = f"manual_{index:03d}"
        if case_id in completed_ids:
            continue
        rag_result = rag_graph.invoke(
            {"question": golden["question"], "documents": [], "answer": ""}
        )
        retrieval_context = render_retrieval_context(rag_result["documents"])
        pending.append(
            LLMTestCase(
                input=golden["question"],
                actual_output=rag_result["answer"],
                retrieval_context=retrieval_context,
                name=case_id,
            )
        )

    with ThreadPoolExecutor(
        max_workers=min(
            get_params().evaluation.component_generator_workers or len(pending) or 1,
            len(pending) or 1,
        )
    ) as executor:
        futures = {
            executor.submit(evaluate_case, test_case, judge_model): test_case.name
            for test_case in pending
        }
        for future in as_completed(futures):
            case_id = futures[future]
            try:
                output["cases"].append(future.result())
            except Exception as error:
                print(f"{case_id} failed and remains pending: {error}")
                continue
            output["cases"].sort(key=lambda case: case["case_id"])
            output["averages"] = {
                name: sum(case["metrics"][name]["score"] for case in output["cases"])
                / len(output["cases"])
                for name in METRIC_NAMES
            }
            output_path.write_text(
                json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(
                f"Saved {len(output['cases'])}/{len(indexed_goldens)} cases to {output_path}"
            )

    if len(output["cases"]) != len(indexed_goldens):
        raise RuntimeError(
            f"Saved {len(output['cases'])}/{len(indexed_goldens)} cases; rerun to retry pending cases."
        )

    output["cases"].sort(key=lambda case: case["case_id"])
    output["averages"] = {
        name: sum(case["metrics"][name]["score"] for case in output["cases"])
        / len(output["cases"])
        for name in METRIC_NAMES
    }

    output["run"]["status"] = "complete"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_markdown_report()
    print("\nCombined results for all cases:")
    for name, average in output["averages"].items():
        passed = sum(case["metrics"][name]["success"] for case in output["cases"])
        print(
            f"- {name}: average={average:.3f}, passed={passed}/{len(output['cases'])}"
        )
    print(f"Saved generator evaluation results to {output_path}")


if __name__ == "__main__":
    main()
