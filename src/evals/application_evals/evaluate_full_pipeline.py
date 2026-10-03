"""Run the complete Coating Compass RAG pipeline through DeepEval.

This command invokes retrieval and generation for every golden case, then
scores the resulting context and answer. It makes paid/networked model calls;
it is intentionally separate from deterministic tests.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import truststore
from deepeval import evaluate
from deepeval.evaluate import AsyncConfig, CacheConfig
from deepeval.test_case import LLMTestCase
from dotenv import load_dotenv

from src.app.basic_rag import (
    RETRIEVAL_K,
    RETRIEVAL_MODES,
    build_retriever,
    create_rag_graph,
    generator_model_config,
    retrieval_metadata,
    retrieval_name,
)
from src.app.prompt_registry import fetch_baseline_prompt
from src.evals.application_evals.metrics import build_full_pipeline_metrics
from src.evals.application_evals.reporting import (
    calculate_averages,
    write_json_report,
    write_markdown_report,
)


GOLDENS_PATH = Path("data/evaluations/manual_golden_dataset.json")
REPORTS_DIRECTORY = Path("reports")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval and generation across the full RAG pipeline."
    )
    parser.add_argument(
        "--goldens",
        type=Path,
        default=GOLDENS_PATH,
        help=f"Reviewed golden dataset (default: {GOLDENS_PATH}).",
    )
    parser.add_argument(
        "--label",
        help="Run label override (default: the resolved retrieval name).",
    )
    parser.add_argument(
        "--retrieval-mode", choices=RETRIEVAL_MODES, default="auto"
    )
    parser.add_argument(
        "--case-id",
        action="append",
        help="Evaluate only this manual_NNN case ID. Repeat to select more than one.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Evaluate only the first N cases for an explicitly approved smoke run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of cases to evaluate concurrently (default: 4).",
    )
    parser.add_argument(
        "--metric-timeout-seconds",
        type=int,
        default=300,
        help="DeepEval deadline for each individual metric call (default: 300).",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume an incomplete JSON artifact without rerunning completed cases.",
    )
    return parser.parse_args()


def validate_goldens(data: Any) -> list[dict[str, Any]]:
    """Fail before paid calls if the evaluation input is malformed."""

    if not isinstance(data, list) or not data:
        raise ValueError("The golden dataset must be a non-empty JSON list.")
    required = {"question", "expected_answer", "expected_context"}
    for index, golden in enumerate(data, start=1):
        if not isinstance(golden, dict):
            raise ValueError(f"Golden case {index} must be a JSON object.")
        missing = sorted(required - golden.keys())
        if missing:
            raise ValueError(f"Golden case {index} is missing fields: {missing}")
        for field in ("question", "expected_answer"):
            if not isinstance(golden[field], str) or not golden[field].strip():
                raise ValueError(
                    f"Golden case {index} {field} must be a non-empty string."
                )
        expected_context = golden["expected_context"]
        if not isinstance(expected_context, list) or not expected_context:
            raise ValueError(
                f"Golden case {index} expected_context must be a non-empty list."
            )
        if any(
            not isinstance(passage, str) or not passage.strip()
            for passage in expected_context
        ):
            raise ValueError(
                f"Golden case {index} expected_context passages must be non-empty strings."
            )
    return data


def load_goldens(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Load, validate, and hash the exact reviewed input before hosted calls."""

    raw = path.read_bytes()
    goldens = validate_goldens(json.loads(raw.decode("utf-8")))
    return goldens, hashlib.sha256(raw).hexdigest()


def validate_resume_input(
    output: dict[str, Any], *, goldens_hash: str, label: str
) -> None:
    """Reject an artifact whose immutable inputs differ from this invocation."""

    if output.get("run", {}).get("goldens_sha256") != goldens_hash:
        raise ValueError("Cannot resume: golden dataset hash has changed.")
    if output["run"].get("label") != label:
        raise ValueError("Cannot resume: --label does not match the saved run.")


def validate_resume_generator(
    output: dict[str, Any], *, provider: str, model: str
) -> None:
    """Prevent one report from combining answers from different generators."""

    run = output.get("run", {})
    saved_model = run.get("generator_model")
    saved_provider = run.get("generator_provider", "groq")
    if saved_provider != provider or saved_model != model:
        raise ValueError(
            "Cannot resume: generator provider or model differs from the saved run."
        )


def validate_resume_retrieval(
    output: dict[str, Any], *, retrieval_config: dict[str, Any]
) -> None:
    run = output.get("run", {})
    if run.get("collection") != retrieval_config["collection"]:
        raise ValueError("Cannot resume: retrieval architecture has changed.")
    saved_mode = run.get("retrieval_mode")
    if saved_mode is not None and saved_mode != retrieval_config["retrieval_mode"]:
        raise ValueError("Cannot resume: retrieval mode has changed.")
    for setting in ("retrieval_k", "bm25_k1", "bm25_b"):
        if run.get(setting) != retrieval_config[setting]:
            raise ValueError(f"Cannot resume: {setting} has changed.")


def render_retrieval_context(documents: list) -> list[str]:
    return [
        f"Source: {document.metadata['source_filename']}, "
        f"page {document.metadata['page_number']}\n{document.page_content}"
        for document in documents
    ]


def close_retriever(retriever) -> None:
    """Close a dense retriever's local Qdrant client; BM25 owns no resources."""

    vector_store = getattr(retriever, "vectorstore", None)
    client = getattr(vector_store, "client", None)
    if client is not None:
        client.close()


def serialize_metric(metric_result) -> dict[str, Any]:
    return {
        "score": metric_result.score,
        "threshold": metric_result.threshold,
        "success": metric_result.success,
        "reason": metric_result.reason,
        "error": metric_result.error,
    }


def empty_answer_metric(metric_name: str) -> dict[str, Any]:
    """Represent an answer-level metric that cannot score an empty answer."""

    return {
        "score": 0.0,
        "threshold": 0.5,
        "success": False,
        "reason": "The baseline generator returned an empty answer.",
        "error": "empty_actual_output",
    }


def invoke_rag_with_backoff(rag_graph, question: str, attempts: int = 4):
    """Retry transient provider rate limits without changing model output."""

    for attempt in range(1, attempts + 1):
        try:
            return rag_graph.invoke(
                {"question": question, "documents": [], "answer": ""}
            )
        except Exception as error:
            is_rate_limit = type(error).__name__ == "RateLimitError" or "429" in str(error)
            if not is_rate_limit or attempt == attempts:
                raise
            delay = 5 * attempt
            print(f"Rate limit for generation; retrying in {delay}s ({attempt}/{attempts})")
            time.sleep(delay)


def evaluate_case(
    *,
    case_id: str,
    golden: dict[str, Any],
    rag_graph,
    judge_model: str,
    hyperparameters: dict[str, Any],
) -> dict[str, Any]:
    """Run retrieval, generation, and all metrics for one golden case."""

    rag_result = invoke_rag_with_backoff(rag_graph, golden["question"])
    retrieval_context = render_retrieval_context(rag_result["documents"])
    test_case = LLMTestCase(
        input=golden["question"],
        actual_output=rag_result["answer"],
        expected_output=golden["expected_answer"],
        context=golden["expected_context"],
        retrieval_context=retrieval_context,
        name=case_id,
    )
    case_output = {
        "case_id": case_id,
        "question": golden["question"],
        "expected_answer": golden["expected_answer"],
        "actual_answer": rag_result["answer"],
        "expected_context": golden["expected_context"],
        "retrieval_context": retrieval_context,
        "metrics": {},
    }

    # A separate call gives each metric its own DeepEval deadline. Keeping the
    # metrics sequential within a case also bounds total judge concurrency.
    for metric in build_full_pipeline_metrics(judge_model):
        metric_name = metric.__name__
        if not str(rag_result["answer"]).strip() and metric_name in {
            "Answer Relevancy",
            "Faithfulness",
            "Answer Simplicity",
            "Answer Correctness",
        }:
            case_output["metrics"][metric_name] = empty_answer_metric(metric_name)
            print(f"Recorded {case_id} {metric_name}=0: empty generator answer")
            continue
        result = evaluate(
            test_cases=[test_case],
            metrics=[metric],
            hyperparameters=hyperparameters,
            async_config=AsyncConfig(run_async=False),
            cache_config=CacheConfig(write_cache=True, use_cache=True),
        )
        metric_result = result.test_results[0].metrics_data[0]
        case_output["metrics"][metric_name] = serialize_metric(metric_result)
        print(
            f"Finished {case_id} metric "
            f"{len(case_output['metrics'])}/7: {metric_name}"
        )
    return case_output


def main() -> None:
    # DeepEval's progress output contains Unicode symbols. Windows automation
    # consoles may otherwise inherit a legacy code page and fail before scoring.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    retrieval_id = retrieval_name(args.retrieval_mode)
    retrieval_config = retrieval_metadata(args.retrieval_mode)
    label = args.label or retrieval_id
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1.")
    if args.workers < 1:
        raise ValueError("--workers must be at least 1.")
    if args.metric_timeout_seconds < 1:
        raise ValueError("--metric-timeout-seconds must be at least 1.")

    # Dataset validation, selection, and resume identity checks intentionally happen
    # before prompt, embedding, generation, or judge clients can make hosted calls.
    goldens, goldens_hash = load_goldens(args.goldens)
    indexed_goldens = list(enumerate(goldens, start=1))
    selected_ids = set(args.case_id or [])
    if selected_ids:
        indexed_goldens = [
            (index, golden)
            for index, golden in indexed_goldens
            if f"manual_{index:03d}" in selected_ids
        ]
        found_ids = {f"manual_{index:03d}" for index, _ in indexed_goldens}
        if missing_ids := selected_ids - found_ids:
            raise ValueError(f"Unknown case IDs: {sorted(missing_ids)}")
    elif args.limit is not None:
        indexed_goldens = indexed_goldens[: args.limit]

    load_dotenv()
    generator_config = generator_model_config()
    generator_provider = generator_config["provider"]
    generator_model = generator_config["model"]

    if args.resume:
        json_path = args.resume
        output = json.loads(json_path.read_text(encoding="utf-8"))
        validate_resume_input(output, goldens_hash=goldens_hash, label=label)
        validate_resume_generator(
            output, provider=generator_provider, model=generator_model
        )
        validate_resume_retrieval(
            output, retrieval_config=retrieval_config
        )

    os.environ["DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE"] = str(
        args.metric_timeout_seconds
    )
    truststore.inject_into_ssl()

    judge_model = os.getenv(
        "COATING_COMPASS_EVALUATION_MODEL", "gpt-5-mini-2025-08-07"
    )
    embedding_model = os.getenv(
        "COATING_COMPASS_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    if retrieval_config["retrieval_mode"] == "contextual-bm25":
        embedding_model = None
    prompt_version = fetch_baseline_prompt()
    retriever = build_retriever(args.retrieval_mode)
    rag_graph = create_rag_graph(retriever, prompt_version.text)

    if args.resume:
        saved_prompt_version = output["run"].get("prompt_version")
        if (
            saved_prompt_version is not None
            and saved_prompt_version != prompt_version.version
        ):
            raise ValueError("Cannot resume: Langfuse prompt version has changed.")
        markdown_path = json_path.with_suffix(".md")
        output["run"]["status"] = "running"
        output["run"].pop("failures", None)
        output["run"]["workers"] = args.workers
        output["run"]["metric_timeout_seconds"] = args.metric_timeout_seconds
        output["run"]["goldens_path"] = str(args.goldens)
        print(f"Resuming {len(output['cases'])}/{len(indexed_goldens)} completed cases")
    else:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        stem = f"full_pipeline_{label}_{timestamp}"
        json_path = REPORTS_DIRECTORY / f"{stem}.json"
        markdown_path = REPORTS_DIRECTORY / f"{stem}.md"
        output = {
            "run": {
                "label": label,
                "timestamp_utc": timestamp,
                "status": "running",
                "prompt_name": prompt_version.name,
                "prompt_label": prompt_version.label,
                "prompt_version": prompt_version.version,
                **retrieval_config,
                "embedding_model": embedding_model,
                "generator_provider": generator_provider,
                "generator_model": generator_model,
                "generator_max_tokens": generator_config["max_tokens"],
                "generator_reasoning_effort": generator_config.get(
                    "reasoning_effort"
                ),
                "judge_model": judge_model,
                "goldens_path": str(args.goldens),
                "goldens_sha256": goldens_hash,
                "case_limit": args.limit,
                "case_ids": sorted(selected_ids),
                "workers": args.workers,
                "metric_timeout_seconds": args.metric_timeout_seconds,
            },
            "averages": {},
            "cases": [],
        }

    hyperparameters = {
        "architecture": label,
        "embedding_model": embedding_model,
        "generator_provider": generator_provider,
        "generator_model": generator_model,
        "generator_max_tokens": generator_config["max_tokens"],
        "generator_reasoning_effort": generator_config.get("reasoning_effort"),
        "judge_model": judge_model,
        "retrieval_k": RETRIEVAL_K,
    }
    completed_ids = {case["case_id"] for case in output["cases"]}
    pending_goldens = [
        (index, golden)
        for index, golden in indexed_goldens
        if f"manual_{index:03d}" not in completed_ids
    ]
    failures = []
    with ThreadPoolExecutor(
        max_workers=min(args.workers, len(pending_goldens) or 1)
    ) as executor:
        futures = {
            executor.submit(
                evaluate_case,
                case_id=f"manual_{index:03d}",
                golden=golden,
                rag_graph=rag_graph,
                judge_model=judge_model,
                hyperparameters=hyperparameters,
            ): f"manual_{index:03d}"
            for index, golden in pending_goldens
        }
        for future in as_completed(futures):
            case_id = futures[future]
            try:
                output["cases"].append(future.result())
                output["cases"].sort(key=lambda case: case["case_id"])
                output["averages"] = calculate_averages(output["cases"])
                write_json_report(json_path, output)
                print(
                    f"Saved {len(output['cases'])}/{len(indexed_goldens)} "
                    "completed cases"
                )
            except Exception as error:
                failure = {
                    "case_id": case_id,
                    "type": type(error).__name__,
                    "message": str(error),
                }
                failures.append(failure)
                output["run"]["failures"] = failures
                write_json_report(json_path, output)

    if failures:
        output["run"]["status"] = "incomplete"
        write_json_report(json_path, output)
        close_retriever(retriever)
        raise RuntimeError(
            f"{len(failures)} case(s) failed; completed cases remain saved at {json_path}"
        )

    output["run"]["status"] = "complete"
    write_json_report(json_path, output)
    write_markdown_report(markdown_path, output)
    close_retriever(retriever)
    print(f"Saved JSON report to {json_path}")
    print(f"Saved Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
