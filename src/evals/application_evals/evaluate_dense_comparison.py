"""Compare both dense modes with shared generator pacing and concurrent judging."""

import argparse
import copy
import hashlib
import json
import logging
import math
import os
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
    RETRIEVAL_K,
    VECTOR_STORE_DIRECTORY,
    build_baseline_vector_store,
    build_contextual_vector_store,
    create_rag_graph,
    generator_model_config,
    retrieval_metadata,
)
from src.app.prompt_registry import fetch_baseline_prompt
from src.evals.application_evals.evaluate_full_pipeline import (
    GOLDENS_PATH,
    evaluate_case,
    load_goldens,
    validate_resume_generator,
    validate_resume_input,
    validate_resume_retrieval,
)
from src.evals.application_evals.metrics import METRIC_NAMES
from src.evals.application_evals.reporting import (
    calculate_averages,
    write_json_report,
    write_markdown_report,
)

logger = logging.getLogger(__name__)


def case_complete(case):
    return set(case.get("metrics", {})) == set(METRIC_NAMES) and all(
        isinstance(metric.get("score"), (int, float))
        and math.isfinite(metric["score"])
        and metric.get("error") in (None, "empty_actual_output")
        for metric in case["metrics"].values()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldens", type=Path, default=GOLDENS_PATH)
    parser.add_argument("--label", default="ab-20261003-parallel")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--generator-rpm", type=float, default=3)
    parser.add_argument("--metric-timeout-seconds", type=int, default=300)
    parser.add_argument("--resume-a", type=Path)
    parser.add_argument("--resume-b", type=Path)
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if args.workers < 1 or args.metric_timeout_seconds < 1:
        raise ValueError("Workers and metric timeout must be positive.")
    if not math.isfinite(args.generator_rpm) or args.generator_rpm <= 0:
        raise ValueError("Generator RPM must be finite and positive.")
    goldens, digest = load_goldens(args.goldens)
    selected = set(args.case_id or [])
    indexed = [(f"manual_{i:03d}", golden) for i, golden in enumerate(goldens, 1)]
    if selected - {case_id for case_id, _ in indexed}:
        raise ValueError("Unknown case IDs.")
    indexed = [(case_id, golden) for case_id, golden in indexed if not selected or case_id in selected]
    load_dotenv()
    truststore.inject_into_ssl()
    config = generator_model_config()
    judge = os.getenv("COATING_COMPASS_EVALUATION_MODEL", "gpt-5-mini-2025-08-07")
    embedding_model = os.getenv("COATING_COMPASS_EMBEDDING_MODEL", "text-embedding-3-small")
    prompt = fetch_baseline_prompt()
    prompt_hash = hashlib.sha256(prompt.text.encode()).hexdigest()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    limiter = InMemoryRateLimiter(requests_per_second=args.generator_rpm / 60, max_bucket_size=1)
    runs = {}
    for tag, mode, resume in [("A", "baseline-dense", args.resume_a), ("B", "contextual-dense", args.resume_b)]:
        label = f"{args.label}-{tag}"
        path = resume or Path("reports", f"full_pipeline_{label}_{timestamp}.json")
        if resume:
            output = json.loads(path.read_text(encoding="utf-8"))
            validate_resume_input(output, goldens_hash=digest, label=label)
            validate_resume_generator(output, provider=config["provider"], model=config["model"])
            validate_resume_retrieval(output, retrieval_config=retrieval_metadata(mode))
            if output["run"].get("case_ids") != [case_id for case_id, _ in indexed]:
                raise ValueError("Cannot resume: selected case IDs differ.")
            for key, value in {"judge_model": judge, "prompt_sha256": prompt_hash,
                               "generator_temperature": config["temperature"],
                               "generator_max_tokens": config["max_tokens"],
                               "generator_reasoning_effort": config.get("reasoning_effort"),
                               "embedding_model": embedding_model}.items():
                if output["run"].get(key) != value:
                    raise ValueError(f"Cannot resume: {key} differs.")
            output["run"].setdefault("previous_attempts", []).append({
                "status": output["run"]["status"],
                "completed_at_utc": output["run"].get("completed_at_utc"),
                "failures": output["run"].get("failures", []),
            })
        else:
            output = {"run": {
                "label": label, "timestamp_utc": timestamp, "status": "running",
                **retrieval_metadata(mode), "embedding_model": embedding_model,
                "generator_provider": config["provider"], "generator_model": config["model"],
                "generator_temperature": config["temperature"],
                "generator_max_tokens": config["max_tokens"],
                "generator_reasoning_effort": config.get("reasoning_effort"),
                "judge_model": judge, "prompt_name": prompt.name, "prompt_label": prompt.label,
                "prompt_version": prompt.version, "prompt_sha256": prompt_hash,
                "goldens_path": str(args.goldens), "goldens_sha256": digest,
                "case_ids": [case_id for case_id, _ in indexed], "case_limit": None,
            }, "cases": [], "averages": {}}
        output["run"].update(status="running", workers=args.workers,
                             generator_rpm=args.generator_rpm, metric_execution="concurrent-a_measure",
                             metric_timeout_seconds=args.metric_timeout_seconds)
        output["run"].pop("failures", None)
        runs[tag] = {"mode": mode, "path": path, "output": output,
                     "cases": {case["case_id"]: case for case in output["cases"]}}
    print(f"[setup] Generator: {config['provider']}/{config['model']}; judge: {judge}", flush=True)
    print(f"[setup] {len(indexed)} questions per mode; {args.workers} case workers; seven concurrent metrics per answer", flush=True)
    print(f"[setup] Shared LangChain generator pacing: {args.generator_rpm:g} requests/min (not an exact token limiter); provider retries handle 429s", flush=True)
    lock = threading.Lock()

    def checkpoint(tag, case):
        with lock:
            run = runs[tag]
            run["cases"][case["case_id"]] = copy.deepcopy(case)
            run["output"]["cases"] = sorted(run["cases"].values(), key=lambda item: item["case_id"])
            complete = [item for item in run["output"]["cases"] if case_complete(item)]
            run["output"]["averages"] = calculate_averages(complete)
            write_json_report(run["path"], run["output"])

    embeddings = OpenAIEmbeddings(model=embedding_model, check_embedding_ctx_length=False,
                                 request_timeout=60, max_retries=2)
    # One native Qdrant client owns the local storage lock for both collections.
    client = QdrantClient(path=str(VECTOR_STORE_DIRECTORY))
    try:
        stores = {
            "A": build_baseline_vector_store(client, embeddings, embedding_model),
            "B": build_contextual_vector_store(client, embeddings),
        }
        graphs = {tag: create_rag_graph(store.as_retriever(search_kwargs={"k": RETRIEVAL_K}),
                                       prompt.text, rate_limiter=limiter)
                  for tag, store in stores.items()}
        jobs = [(tag, case_id, golden) for case_id, golden in indexed for tag in runs
                if not case_complete(runs[tag]["cases"].get(case_id, {}))]
        failures = []
        with ThreadPoolExecutor(max_workers=min(args.workers, len(jobs) or 1)) as executor:
            futures = {executor.submit(
                evaluate_case, case_id=case_id, golden=golden, rag_graph=graphs[tag],
                judge_model=judge, hyperparameters={"progress_prefix": f"[{tag}]",
                    "metric_timeout_seconds": args.metric_timeout_seconds},
                checkpoint=lambda case, tag=tag: checkpoint(tag, case),
                existing_case=copy.deepcopy(runs[tag]["cases"].get(case_id)),
            ): (tag, case_id) for tag, case_id, golden in jobs}
            for future in as_completed(futures):
                tag, case_id = futures[future]
                try:
                    result = future.result()
                    checkpoint(tag, result)
                    if not case_complete(result):
                        raise ValueError("The case did not produce seven finite metric scores.")
                except Exception as error:
                    logger.exception("[%s] %s failed; retaining completed checkpoints", tag, case_id)
                    failures.append({"tag": tag, "case_id": case_id,
                                     "type": type(error).__name__, "message": str(error)})
                    print(f"[{tag}] {case_id} FAILED: {type(error).__name__}: {error}", flush=True)
                with lock:
                    completed = sum(case_complete(case) for case in runs[tag]["cases"].values())
                print(f"[{tag}] Progress: {completed}/{len(indexed)} questions complete", flush=True)
        for tag, run in runs.items():
            own_failures = [failure for failure in failures if failure["tag"] == tag]
            run["output"]["run"].update(status="incomplete" if own_failures else "complete",
                                         completed_at_utc=datetime.now(UTC).isoformat(),
                                         failures=own_failures)
            write_json_report(run["path"], run["output"])
            if not own_failures:
                write_markdown_report(run["path"].with_suffix(".md"), run["output"])
            print(f"[{tag}] Saved {run['output']['run']['status']} report: {run['path']}", flush=True)
        if failures:
            raise RuntimeError(f"{len(failures)} case(s) failed; answers and completed metrics are checkpointed.")
        print("[summary] Both A and B completed.", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
