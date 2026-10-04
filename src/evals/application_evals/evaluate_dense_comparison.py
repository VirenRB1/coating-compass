"""Compare both dense modes with shared generator pacing and concurrent judging."""

import argparse
import copy
import hashlib
import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import truststore
from dotenv import load_dotenv
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from src.app.basic_rag import (
    build_baseline_vector_store,
    build_contextual_vector_store,
    create_rag_graph,
    generator_model_config,
    retrieval_metadata,
)
from src.app.prompt_registry import fetch_baseline_prompt
from src.config import (
    add_params_argument,
    config_snapshot,
    get_params,
    load_params,
    select_cases,
    validate_resume_config,
)
from src.config import path as config_path
from src.evals.application_evals.evaluate_full_pipeline import (
    evaluate_case,
    load_goldens,
    validate_resume_generator,
    validate_resume_input,
    validate_resume_retrieval,
)
from src.evals.application_evals.reporting import (
    calculate_averages,
    case_complete,
    write_json_report,
    write_markdown_report,
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_params_argument(parser)
    parser.add_argument("--label", help="Comparison run label.")
    parser.add_argument("--resume-a", type=Path)
    parser.add_argument("--resume-b", type=Path)
    args = parser.parse_args()
    settings = load_params(args.params)
    args.label = args.label or settings.evaluation.comparison_label
    args.goldens = config_path("goldens")
    args.case_id = settings.evaluation.case_ids
    args.workers = settings.evaluation.comparison_workers
    args.generator_rpm = settings.evaluation.generator_rpm
    args.metric_timeout_seconds = settings.evaluation.metric_timeout_seconds
    # Check resume identity before Langfuse or any model client can make requests.
    for resume in (args.resume_a, args.resume_b):
        if resume:
            validate_resume_config(
                json.loads(resume.read_text(encoding="utf-8"))["run"]
            )
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    goldens, digest = load_goldens(args.goldens)
    indexed = [(f"manual_{i:03d}", golden) for i, golden in select_cases(goldens)]
    load_dotenv()
    truststore.inject_into_ssl()
    config = generator_model_config()
    judge = settings.evaluation.judge_model
    embedding_model = settings.embeddings.model
    prompt = fetch_baseline_prompt()
    prompt_hash = hashlib.sha256(prompt.text.encode()).hexdigest()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    limiter = InMemoryRateLimiter(
        requests_per_second=args.generator_rpm / 60, max_bucket_size=1
    )
    runs = {}
    for tag, mode, resume in [
        ("A", settings.evaluation.comparison_modes[0], args.resume_a),
        ("B", settings.evaluation.comparison_modes[1], args.resume_b),
    ]:
        label = f"{args.label}-{tag}"
        path = (
            resume or config_path("reports") / f"full_pipeline_{label}_{timestamp}.json"
        )
        if resume:
            output = json.loads(path.read_text(encoding="utf-8"))
            validate_resume_input(output, goldens_hash=digest, label=label)
            validate_resume_generator(
                output, provider=config["provider"], model=config["model"]
            )
            validate_resume_retrieval(output, retrieval_config=retrieval_metadata(mode))
            if output["run"].get("case_ids") != [case_id for case_id, _ in indexed]:
                raise ValueError("Cannot resume: selected case IDs differ.")
            for key, value in {
                "judge_model": judge,
                "prompt_sha256": prompt_hash,
                "generator_temperature": config["temperature"],
                "generator_max_tokens": config["max_tokens"],
                "generator_reasoning_effort": config.get("reasoning_effort"),
                "embedding_model": embedding_model,
            }.items():
                if output["run"].get(key) != value:
                    raise ValueError(f"Cannot resume: {key} differs.")
            output["run"].setdefault("previous_attempts", []).append(
                {
                    "status": output["run"]["status"],
                    "completed_at_utc": output["run"].get("completed_at_utc"),
                    "failures": output["run"].get("failures", []),
                }
            )
        else:
            output = {
                "run": {
                    **config_snapshot(),
                    "label": label,
                    "timestamp_utc": timestamp,
                    "status": "running",
                    **retrieval_metadata(mode),
                    "embedding_model": embedding_model,
                    "generator_provider": config["provider"],
                    "generator_model": config["model"],
                    "generator_temperature": config["temperature"],
                    "generator_max_tokens": config["max_tokens"],
                    "generator_reasoning_effort": config.get("reasoning_effort"),
                    "judge_model": judge,
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_sha256": prompt_hash,
                    "goldens_path": str(args.goldens),
                    "goldens_sha256": digest,
                    "case_ids": [case_id for case_id, _ in indexed],
                    "case_limit": settings.evaluation.limit,
                },
                "cases": [],
                "averages": {},
            }
        output["run"].update(
            status="running",
            workers=args.workers,
            generator_rpm=args.generator_rpm,
            metric_execution="concurrent-a_measure",
            metric_timeout_seconds=args.metric_timeout_seconds,
        )
        output["run"].pop("failures", None)
        runs[tag] = {
            "mode": mode,
            "path": path,
            "output": output,
            "cases": {case["case_id"]: case for case in output["cases"]},
        }
    print(
        f"[setup] Generator: {config['provider']}/{config['model']}; judge: {judge}",
        flush=True,
    )
    print(
        f"[setup] {len(indexed)} questions per mode; {args.workers} case workers; seven concurrent metrics per answer",
        flush=True,
    )
    print(
        f"[setup] Shared LangChain generator pacing: {args.generator_rpm:g} requests/min (not an exact token limiter); provider retries handle 429s",
        flush=True,
    )
    lock = threading.Lock()

    def checkpoint(tag, case):
        with lock:
            run = runs[tag]
            run["cases"][case["case_id"]] = copy.deepcopy(case)
            run["output"]["cases"] = sorted(
                run["cases"].values(), key=lambda item: item["case_id"]
            )
            complete = [item for item in run["output"]["cases"] if case_complete(item)]
            run["output"]["averages"] = calculate_averages(complete)
            write_json_report(run["path"], run["output"])

    config_path("vector_store").mkdir(parents=True, exist_ok=True)
    embeddings = OpenAIEmbeddings(
        model=embedding_model,
        check_embedding_ctx_length=False,
        request_timeout=settings.embeddings.timeout_seconds,
        max_retries=settings.embeddings.max_retries,
        dimensions=settings.embeddings.dimensions,
    )
    # One native Qdrant client owns the local storage lock for both collections.
    client = QdrantClient(path=str(config_path("vector_store")))
    try:
        stores = {}
        for tag, run in runs.items():
            stores[tag] = (
                build_baseline_vector_store(client, embeddings, embedding_model)
                if run["mode"] == "baseline-dense"
                else build_contextual_vector_store(client, embeddings)
            )
        graphs = {
            tag: create_rag_graph(
                store.as_retriever(search_kwargs={"k": get_params().retrieval.k}),
                prompt.text,
                rate_limiter=limiter,
            )
            for tag, store in stores.items()
        }
        jobs = [
            (tag, case_id, golden)
            for case_id, golden in indexed
            for tag in runs
            if not case_complete(runs[tag]["cases"].get(case_id, {}))
        ]
        failures = []
        with ThreadPoolExecutor(
            max_workers=min(args.workers, len(jobs) or 1)
        ) as executor:
            futures = {
                executor.submit(
                    evaluate_case,
                    case_id=case_id,
                    golden=golden,
                    rag_graph=graphs[tag],
                    judge_model=judge,
                    hyperparameters={
                        "progress_prefix": f"[{tag}]",
                        "metric_timeout_seconds": args.metric_timeout_seconds,
                    },
                    checkpoint=lambda case, tag=tag: checkpoint(tag, case),
                    existing_case=copy.deepcopy(runs[tag]["cases"].get(case_id)),
                ): (tag, case_id)
                for tag, case_id, golden in jobs
            }
            for future in as_completed(futures):
                tag, case_id = futures[future]
                try:
                    result = future.result()
                    checkpoint(tag, result)
                    if not case_complete(result):
                        raise ValueError(
                            "The case did not produce seven finite metric scores."
                        )
                except Exception as error:
                    logger.exception(
                        "[%s] %s failed; retaining completed checkpoints", tag, case_id
                    )
                    failures.append(
                        {
                            "tag": tag,
                            "case_id": case_id,
                            "type": type(error).__name__,
                            "message": str(error),
                        }
                    )
                    print(
                        f"[{tag}] {case_id} FAILED: {type(error).__name__}: {error}",
                        flush=True,
                    )
                with lock:
                    completed = sum(
                        case_complete(case) for case in runs[tag]["cases"].values()
                    )
                print(
                    f"[{tag}] Progress: {completed}/{len(indexed)} questions complete",
                    flush=True,
                )
        for tag, run in runs.items():
            own_failures = [failure for failure in failures if failure["tag"] == tag]
            run["output"]["run"].update(
                status="incomplete" if own_failures else "complete",
                completed_at_utc=datetime.now(UTC).isoformat(),
                failures=own_failures,
            )
            write_json_report(run["path"], run["output"])
            if not own_failures:
                write_markdown_report(run["path"].with_suffix(".md"), run["output"])
            print(
                f"[{tag}] Saved {run['output']['run']['status']} report: {run['path']}",
                flush=True,
            )
        if failures:
            raise RuntimeError(
                f"{len(failures)} case(s) failed; answers and completed metrics are checkpointed."
            )
        print("[summary] Both A and B completed.", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
