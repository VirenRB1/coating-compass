"""Run the complete Coating Compass RAG pipeline through DeepEval.

This command invokes retrieval and generation for every golden case, then
scores the resulting context and answer. It makes paid/networked model calls;
it is intentionally separate from deterministic tests.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import truststore
from deepeval.test_case import LLMTestCase
from dotenv import load_dotenv
from langchain_core.rate_limiters import InMemoryRateLimiter

from src.app.basic_rag import (
    build_retriever,
    create_rag_graph,
    generator_model_config,
    retrieval_metadata,
    retrieval_name,
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
from src.evals.application_evals.metrics import build_full_pipeline_metrics
from src.evals.application_evals.reporting import (
    calculate_averages,
    case_complete,
    write_json_report,
    write_markdown_report,
)
from src.evals.tracking import track_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval and generation across the full RAG pipeline."
    )
    add_params_argument(parser)
    parser.add_argument(
        "--label", help="Run label (default: resolved retrieval identity)."
    )
    parser.add_argument(
        "--resume", type=Path, help="Resume a report with identical validated settings."
    )
    args = parser.parse_args()
    settings = load_params(args.params)
    args.goldens = config_path("goldens")
    args.retrieval_mode = settings.retrieval.mode
    args.case_id, args.limit = settings.evaluation.case_ids, settings.evaluation.limit
    args.workers = settings.evaluation.workers
    args.metric_timeout_seconds = settings.evaluation.metric_timeout_seconds
    return args


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
    for setting in (
        "retrieval_k",
        "bm25_k1",
        "bm25_b",
        "bm25_implementation",
        "hybrid_implementation",
        "hybrid_dense_k",
        "hybrid_bm25_k",
        "hybrid_weights",
        "hybrid_rrf_c",
        "reranking_model",
        "reranking_implementation",
    ):
        if run.get(setting) != retrieval_config[setting]:
            raise ValueError(f"Cannot resume: {setting} has changed.")


def close_retriever(retriever) -> None:
    """Close dense clients inside native retrievers or composed hybrid branches."""

    base = getattr(retriever, "base_retriever", None)
    if base is not None:
        close_retriever(base)
    compressor = getattr(retriever, "base_compressor", None)
    reranking_client = getattr(compressor, "client", None)
    if reranking_client is not None:
        reranking_client.close()
    for child in getattr(retriever, "steps", []) or getattr(
        retriever, "retrievers", []
    ):
        close_retriever(child)

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
        "threshold": metric_threshold(metric_name),
        "success": False,
        "reason": "The baseline generator returned an empty answer.",
        "error": "empty_actual_output",
    }


def invoke_rag_with_backoff(rag_graph, question: str, attempts: int | None = None):
    """Retry transient provider rate limits without changing model output."""

    settings = get_params().evaluation
    attempts = settings.generation_attempts if attempts is None else attempts
    for attempt in range(1, attempts + 1):
        try:
            return rag_graph.invoke(
                {"question": question, "documents": [], "answer": ""}
            )
        except Exception as error:
            is_rate_limit = type(error).__name__ == "RateLimitError" or "429" in str(
                error
            )
            if not is_rate_limit or attempt == attempts:
                raise
            delay = settings.generation_backoff_seconds * attempt
            print(
                f"Rate limit for generation; retrying in {delay}s ({attempt}/{attempts})"
            )
            time.sleep(delay)


async def measure_case_metrics(
    test_case, metrics, case_output, *, timeout, prefix, checkpoint=None
):
    """Run independent DeepEval async metrics together; retain partial failures."""

    async def measure(metric):
        name = metric.__name__
        saved = case_output["metrics"].get(name)
        if saved and saved.get("error") is None and saved.get("score") is not None:
            return
        if not str(test_case.actual_output).strip() and name in {
            "Answer Relevancy",
            "Faithfulness",
            "Answer Simplicity",
            "Answer Correctness",
        }:
            case_output["metrics"][name] = empty_answer_metric(name)
        else:
            print(f"{prefix} judge started: {name}", flush=True)
            try:
                await asyncio.wait_for(
                    metric.a_measure(
                        test_case, _show_indicator=False, _log_metric_to_confident=False
                    ),
                    timeout=timeout,
                )
                case_output["metrics"][name] = serialize_metric(metric)
                case_output["metrics"][name]["evaluation_cost"] = metric.evaluation_cost
            except Exception as error:
                case_output["metrics"][name] = {
                    "score": None,
                    "threshold": metric.threshold,
                    "success": False,
                    "reason": None,
                    "error": f"{type(error).__name__}: {error}",
                }
                if checkpoint:
                    checkpoint(case_output)
                print(
                    f"{prefix} judge failed: {name}: {type(error).__name__}", flush=True
                )
                raise
        if checkpoint:
            checkpoint(case_output)
        print(
            f"{prefix} judge finished: {name}={case_output['metrics'][name]['score']}",
            flush=True,
        )

    results = await asyncio.gather(
        *(measure(metric) for metric in metrics), return_exceptions=True
    )
    errors = [result for result in results if isinstance(result, Exception)]
    if errors:
        raise RuntimeError(
            f"{len(errors)} metric(s) failed: {type(errors[0]).__name__}: {errors[0]}"
        ) from errors[0]


def evaluate_case(
    *,
    case_id: str,
    golden: dict[str, Any],
    rag_graph,
    judge_model: str,
    hyperparameters: dict[str, Any],
    checkpoint=None,
    existing_case=None,
) -> dict[str, Any]:
    """Run retrieval, generation, and all metrics for one golden case."""

    prefix = f"{hyperparameters.get('progress_prefix', '')} {case_id}".strip()
    if existing_case is None:
        print(f"{prefix} queued for retrieval/generation", flush=True)
        rag_result = invoke_rag_with_backoff(rag_graph, golden["question"])
        retrieval_context = render_retrieval_context(rag_result["documents"])
        case_output = {
            "case_id": case_id,
            "question": golden["question"],
            "expected_answer": golden["expected_answer"],
            "actual_answer": rag_result["answer"],
            "expected_context": golden["expected_context"],
            "retrieval_context": retrieval_context,
            "metrics": {},
        }
        print(
            f"{prefix} generation finished: {len(str(rag_result['answer']))} answer characters",
            flush=True,
        )
    else:
        if existing_case["question"] != golden["question"]:
            raise ValueError("Saved case question does not match the golden dataset.")
        case_output = existing_case
        print(f"{prefix} reusing checkpointed answer and completed metrics", flush=True)
    if checkpoint:
        checkpoint(case_output)
    test_case = LLMTestCase(
        input=golden["question"],
        actual_output=case_output["actual_answer"],
        expected_output=golden["expected_answer"],
        context=golden["expected_context"],
        retrieval_context=case_output["retrieval_context"],
        name=case_id,
    )

    # HTTP judging needs sockets only. On Windows, avoid Proactor completion
    # callbacks racing with per-worker loop teardown (WinError 995/InvalidState).
    asyncio.run(
        measure_case_metrics(
            test_case,
            build_full_pipeline_metrics(judge_model, async_mode=True),
            case_output,
            timeout=get_params().evaluation.metric_timeout_seconds,
            prefix=prefix,
            checkpoint=checkpoint,
        ),
        loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None,
    )
    return case_output


def main() -> None:
    # DeepEval's progress output contains Unicode symbols. Windows automation
    # consoles may otherwise inherit a legacy code page and fail before scoring.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    with track_experiment(args.params, args.label) as tracker:
        run_evaluation(args, tracker)


def run_evaluation(args, tracker) -> None:
    retrieval_id = retrieval_name(args.retrieval_mode)
    retrieval_config = retrieval_metadata(args.retrieval_mode)
    label = args.label or retrieval_id

    # Dataset validation, selection, and resume identity checks intentionally happen
    # before prompt, embedding, generation, or judge clients can make hosted calls.
    goldens, goldens_hash = load_goldens(args.goldens)
    tracker.log_goldens(args.goldens)
    indexed_goldens = select_cases(goldens)
    selected_ids = set(args.case_id or [])

    load_dotenv()
    generator_config = generator_model_config()
    generator_provider = generator_config["provider"]
    generator_model = generator_config["model"]

    if args.resume:
        json_path = args.resume
        output = json.loads(json_path.read_text(encoding="utf-8"))
        validate_resume_config(output["run"])
        validate_resume_input(output, goldens_hash=goldens_hash, label=label)
        validate_resume_generator(
            output, provider=generator_provider, model=generator_model
        )
        validate_resume_retrieval(output, retrieval_config=retrieval_config)

    os.environ["DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE"] = str(
        args.metric_timeout_seconds
    )
    truststore.inject_into_ssl()

    judge_model = get_params().evaluation.judge_model
    embedding_model = get_params().embeddings.model
    if retrieval_config["retrieval_mode"] == "contextual-bm25":
        embedding_model = None
    prompt_version = fetch_baseline_prompt()
    tracker.log_prompt(prompt_version)

    if args.resume:
        saved_prompt_version = output["run"].get("prompt_version")
        if (
            saved_prompt_version is not None
            and saved_prompt_version != prompt_version.version
        ):
            raise ValueError("Cannot resume: Langfuse prompt version has changed.")
        markdown_path = json_path.with_suffix(".md")
        output["run"].setdefault("previous_attempts", []).append(
            {
                "status": output["run"]["status"],
                "failures": copy.deepcopy(output["run"].get("failures", [])),
            }
        )
        output["run"]["status"] = "running"
        output["run"].pop("failures", None)
        output["run"]["workers"] = args.workers
        output["run"]["metric_timeout_seconds"] = args.metric_timeout_seconds
        output["run"]["goldens_path"] = str(args.goldens)
        print(
            f"Resuming {sum(case_complete(case) for case in output['cases'])}/{len(indexed_goldens)} completed cases; {len(output['cases'])} answers saved"
        )
    else:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        stem = f"full_pipeline_{label}_{timestamp}"
        json_path = config_path("reports") / f"{stem}.json"
        markdown_path = config_path("reports") / f"{stem}.md"
        output = {
            "run": {
                **config_snapshot(),
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
                "generator_reasoning_effort": generator_config.get("reasoning_effort"),
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
        "retrieval_k": get_params().retrieval.k,
        "metric_timeout_seconds": args.metric_timeout_seconds,
    }
    saved_cases = {case["case_id"]: case for case in output["cases"]}
    completed_ids = {
        case_id for case_id, case in saved_cases.items() if case_complete(case)
    }
    checkpoint_lock = threading.Lock()

    def checkpoint(case):
        with checkpoint_lock:
            saved_cases[case["case_id"]] = copy.deepcopy(case)
            output["cases"] = sorted(
                saved_cases.values(), key=lambda item: item["case_id"]
            )
            output["averages"] = calculate_averages(
                [item for item in output["cases"] if case_complete(item)]
            )
            write_json_report(json_path, output)

    pending_goldens = [
        (index, golden)
        for index, golden in indexed_goldens
        if f"manual_{index:03d}" not in completed_ids
    ]
    retriever, rag_graph = None, None
    if any(f"manual_{index:03d}" not in saved_cases for index, _ in pending_goldens):
        retriever = build_retriever(args.retrieval_mode)
        limiter = InMemoryRateLimiter(
            requests_per_second=get_params().evaluation.generator_rpm / 60,
            max_bucket_size=1,
        )
        rag_graph = create_rag_graph(
            retriever, prompt_version.text, rate_limiter=limiter
        )
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
                checkpoint=checkpoint,
                existing_case=copy.deepcopy(saved_cases.get(f"manual_{index:03d}")),
            ): f"manual_{index:03d}"
            for index, golden in pending_goldens
        }
        for future in as_completed(futures):
            case_id = futures[future]
            try:
                result = future.result()
                checkpoint(result)
                if not case_complete(result):
                    raise ValueError("Case did not produce seven finite metric scores.")
                print(
                    f"Saved {sum(case_complete(case) for case in output['cases'])}/{len(indexed_goldens)} "
                    "completed cases"
                )
            except Exception as error:
                failure = {
                    "case_id": case_id,
                    "type": type(error).__name__,
                    "message": str(error),
                }
                with checkpoint_lock:
                    failures.append(failure)
                    output["run"]["failures"] = failures
                    write_json_report(json_path, output)

    if failures:
        output["run"]["status"] = "incomplete"
        write_json_report(json_path, output)
        close_retriever(retriever)
        tracker.log_results(output, json_path)
        raise RuntimeError(
            f"{len(failures)} case(s) failed; completed cases remain saved at {json_path}"
        )

    output["run"]["status"] = "complete"
    write_json_report(json_path, output)
    write_markdown_report(markdown_path, output)
    close_retriever(retriever)
    tracker.log_results(output, json_path)
    print(f"Saved JSON report to {json_path}")
    print(f"Saved Markdown report to {markdown_path}")


if __name__ == "__main__":
    main()
