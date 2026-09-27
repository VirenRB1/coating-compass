"""Create resumable, auditable contextual-retrieval records.

Dry runs only extract and validate local sources. Generation is an explicit hosted
Groq operation and is never started by the application ingestion path.
"""

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import truststore
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.data.corpus import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    extract_pages,
    load_manifest_metadata,
    render_full_document,
    source_paths,
    split_pages,
    stable_chunk_id,
)


KB_VERSION = "contextual-dense-v1"
GROQ_MODEL = "openai/gpt-oss-20b"
OPENAI_MODEL = "gpt-5-mini"
CONTEXT_MODELS = {GROQ_MODEL, OPENAI_MODEL}
OUTPUT_DIRECTORY = Path("data/processed/contextual_dense_v1")
RECORDS_DIRECTORY = OUTPUT_DIRECTORY / "records"
MANIFEST_PATH = OUTPUT_DIRECTORY / "manifest.json"
COMPACT_CHUNKS_PATH = OUTPUT_DIRECTORY / "chunks.jsonl"
MIN_CONTEXT_TOKENS = 50
MAX_CONTEXT_TOKENS = 120
MAX_ATTEMPTS = 5
PROMPT = """You create retrieval-only context for one chunk from a manufacturer PDF.
Using only the supplied document, write 50-100 tokens that identify what this chunk
is about and where it belongs in the document. Do not add facts, advice, or claims
that are absent from the document. The context is synthetic retrieval metadata, not
manufacturer evidence. Return JSON with one field named context."""
PROMPT_HASH = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()


class ContextResponse(BaseModel):
    context: str = Field(min_length=1)


@dataclass
class DocumentWork:
    path: Path
    pages: list[Document]
    chunks: list[Document]


class ProviderQuotaError(RuntimeError):
    """Stop the corpus run when the selected provider has no quota left."""


class GroqRequestTooLargeError(RuntimeError):
    """Use OpenAI when one full-document Groq request exceeds its tier limit."""


def approximate_token_count(text: str) -> int:
    """Count word/punctuation units without adding a model-specific tokenizer."""

    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def record_path(document_hash: str) -> Path:
    return RECORDS_DIRECTORY / f"{document_hash}.jsonl"


def read_latest_records() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not RECORDS_DIRECTORY.exists():
        return latest
    for path in sorted(RECORDS_DIRECTORY.glob("*.jsonl")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {error}") from error
            latest[record["chunk_id"]] = record
    return latest


def append_record(record: dict[str, Any]) -> None:
    RECORDS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = record_path(record["document_sha256"])
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        output.flush()


def inventory() -> tuple[list[DocumentWork], dict[str, str]]:
    metadata = load_manifest_metadata()
    items: list[DocumentWork] = []
    source_hashes: dict[str, str] = {}
    for path in source_paths():
        pages = extract_pages(path, metadata[path.name])
        chunks = split_pages(pages)
        source_hashes[path.name] = metadata[path.name]["document_sha256"]
        items.append(
            DocumentWork(
                path=path,
                pages=pages,
                chunks=chunks,
            )
        )
    return items, source_hashes


def valid_success(record: dict[str, Any], chunk: Document) -> bool:
    return (
        record.get("status") == "complete"
        and record.get("prompt_sha256") == PROMPT_HASH
        and record.get("model") in CONTEXT_MODELS
        and record.get("document_sha256") == chunk.metadata["document_sha256"]
        and record.get("source_filename") == chunk.metadata["source_filename"]
        and record.get("page_number") == chunk.metadata["page_number"]
        and record.get("start_index") == chunk.metadata.get("start_index", 0)
        and record.get("original_text_sha256")
        == hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest()
        and MIN_CONTEXT_TOKENS
        <= approximate_token_count(record.get("generated_context", ""))
        <= MAX_CONTEXT_TOKENS
    )


def build_manifest(
    items: list[DocumentWork],
    latest: dict[str, dict[str, Any]],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    expected = {
        stable_chunk_id(chunk): chunk
        for item in items
        for chunk in item.chunks
    }
    counts = Counter(
        "complete" if valid_success(latest.get(identifier, {}), chunk) else "unresolved"
        for identifier, chunk in expected.items()
    )
    complete = counts["unresolved"] == 0 and len(latest) == len(expected)
    return {
        "schema_version": 1,
        "knowledge_base_version": KB_VERSION,
        "completion_state": "complete" if complete else "partial",
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "source_hashes": source_hashes,
        "chunk_settings": {"size": CHUNK_SIZE, "overlap": CHUNK_OVERLAP},
        "context_settings": {
            "models": sorted(CONTEXT_MODELS),
            "prompt_sha256": PROMPT_HASH,
            "min_approx_tokens": MIN_CONTEXT_TOKENS,
            "max_approx_tokens": MAX_CONTEXT_TOKENS,
        },
        "counts": {
            "documents": len(items),
            "chunks": len(expected),
            "completed": counts["complete"],
            "unresolved": counts["unresolved"],
        },
    }


def write_manifest(manifest: dict[str, Any]) -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(MANIFEST_PATH)


def write_compact_chunks(
    items: list[DocumentWork], latest: dict[str, dict[str, Any]]
) -> None:
    """Write one current successful record per chunk after full completion."""

    records = [
        latest[stable_chunk_id(chunk)]
        for item in items
        for chunk in item.chunks
    ]
    temporary = COMPACT_CHUNKS_PATH.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(COMPACT_CHUNKS_PATH)


def generator(provider: str) -> tuple[Any, str]:
    if provider == "groq":
        model_name = GROQ_MODEL
        model = ChatGroq(
            model=model_name,
            temperature=0,
            max_tokens=300,
            timeout=60,
            max_retries=0,
            reasoning_effort="low",
        )
    else:
        model_name = OPENAI_MODEL
        model = ChatOpenAI(
            model=model_name,
            max_tokens=300,
            timeout=60,
            max_retries=0,
            reasoning_effort="low",
        )
    chain = model.with_structured_output(ContextResponse, method="json_schema")
    return chain, model_name


def retry_delay_seconds(error: Exception, attempt: int) -> float:
    """Use Groq's requested wait for rate limits, otherwise use short backoff."""

    match = re.search(r"try again in ([0-9.]+)s", str(error), flags=re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1
    return 2 ** (attempt - 1)


def quota_is_exhausted(error: Exception, provider: str) -> bool:
    message = str(error).lower()
    if provider == "groq":
        return "tokens per day (tpd)" in message
    return any(
        marker in message
        for marker in ("insufficient_quota", "billing_hard_limit_reached")
    )


def groq_request_is_too_large(error: Exception, provider: str) -> bool:
    return provider == "groq" and "request too large" in str(error).lower()


def generate_context(
    chain: Any, document_text: str, chunk_text: str, provider: str
) -> tuple[str, int]:
    prompt = ChatPromptTemplate.from_messages(
        [
            # Keep the stable instructions and full document before the varying
            # chunk so providers can reuse the repeated prompt prefix.
            ("system", PROMPT),
            ("human", "<document>\n{document}\n</document>"),
            ("human", "<chunk>\n{chunk}\n</chunk>\n{length_feedback}"),
        ]
    )
    last_error: Exception | None = None
    length_feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = chain.invoke(
                prompt.invoke(
                    {
                        "document": document_text,
                        "chunk": chunk_text,
                        "length_feedback": length_feedback,
                    }
                )
            )
            context = response.context.strip()
            count = approximate_token_count(context)
            if not MIN_CONTEXT_TOKENS <= count <= MAX_CONTEXT_TOKENS:
                length_feedback = (
                    f"Your previous response was {count} approximate tokens. "
                    f"Revise it to {MIN_CONTEXT_TOKENS}-{MAX_CONTEXT_TOKENS} tokens."
                )
                raise ValueError(
                    f"Context has {count} approximate tokens; expected "
                    f"{MIN_CONTEXT_TOKENS}-{MAX_CONTEXT_TOKENS}."
                )
            return context, attempt
        except Exception as error:
            last_error = error
            if groq_request_is_too_large(error, provider):
                raise GroqRequestTooLargeError(str(error)) from error
            if quota_is_exhausted(error, provider):
                raise ProviderQuotaError(str(error)) from error
            if attempt < MAX_ATTEMPTS:
                time.sleep(retry_delay_seconds(error, attempt))
    raise RuntimeError(f"Context generation failed after {MAX_ATTEMPTS} attempts: {last_error}")


def base_record(
    chunk: Document, model_name: str, provider: str
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "chunk_id": stable_chunk_id(chunk),
        "document_sha256": chunk.metadata["document_sha256"],
        "source_filename": chunk.metadata["source_filename"],
        "source_url": chunk.metadata["source_url"],
        "page_number": chunk.metadata["page_number"],
        "start_index": chunk.metadata.get("start_index", 0),
        "original_text": chunk.page_content,
        "original_text_sha256": hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest(),
        "model": model_name,
        "provider": provider,
        "prompt_sha256": PROMPT_HASH,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate contextual dense-retrieval records.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without API calls or writes.")
    parser.add_argument("--document", help="Generate only the exact source PDF filename.")
    parser.add_argument(
        "--confirm-paid-calls",
        action="store_true",
        help="Required acknowledgement before hosted context generation begins.",
    )
    parser.add_argument(
        "--provider",
        choices=("groq", "openai", "auto"),
        default="groq",
        help="Hosted provider; auto starts with Groq and falls back to OpenAI.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    items, source_hashes = inventory()
    latest = read_latest_records()
    manifest = build_manifest(items, latest, source_hashes)
    print(f"Validated {manifest['counts']['documents']} documents and {manifest['counts']['chunks']} chunks.")
    print(f"Completed: {manifest['counts']['completed']}; unresolved: {manifest['counts']['unresolved']}.")
    if args.dry_run:
        return
    if not args.confirm_paid_calls:
        raise ValueError(
            "Hosted generation requires explicit approval via --confirm-paid-calls."
        )

    selected = items
    if args.document:
        selected = [item for item in items if item.path.name == args.document]
        if not selected:
            raise ValueError(f"Document is not in the source corpus: {args.document}")

    truststore.inject_into_ssl()
    load_dotenv()
    provider_names = ("groq", "openai") if args.provider == "auto" else (args.provider,)
    generators = {
        provider: generator(provider)
        for provider in provider_names
    }
    active_provider = provider_names[0]
    for item in selected:
        document_text = render_full_document(item.pages)
        print(f"Contextualizing {item.path.name} ({len(item.chunks)} chunks)...")
        for chunk in item.chunks:
            identifier = stable_chunk_id(chunk)
            if valid_success(latest.get(identifier, {}), chunk):
                continue
            chain, model_name = generators[active_provider]
            record = base_record(chunk, model_name, active_provider)
            try:
                try:
                    context, attempts = generate_context(
                        chain, document_text, chunk.page_content, active_provider
                    )
                except GroqRequestTooLargeError:
                    if args.provider != "auto":
                        raise
                    fallback_chain, fallback_model = generators["openai"]
                    record["model"] = fallback_model
                    record["provider"] = "openai"
                    context, attempts = generate_context(
                        fallback_chain, document_text, chunk.page_content, "openai"
                    )
                except ProviderQuotaError:
                    if args.provider != "auto" or active_provider != "groq":
                        raise
                    active_provider = "openai"
                    fallback_chain, fallback_model = generators[active_provider]
                    record["model"] = fallback_model
                    record["provider"] = active_provider
                    context, attempts = generate_context(
                        fallback_chain,
                        document_text,
                        chunk.page_content,
                        active_provider,
                    )
                record.update(
                    status="complete",
                    generated_context=context,
                    context_approx_tokens=approximate_token_count(context),
                    attempts=attempts,
                    error=None,
                )
            except ProviderQuotaError as error:
                record.update(
                    status="failed",
                    generated_context=None,
                    context_approx_tokens=0,
                    attempts=1,
                    error=str(error),
                )
                append_record(record)
                latest[identifier] = record
                write_manifest(build_manifest(items, latest, source_hashes))
                raise SystemExit(
                    f"{record['provider'].title()} quota exhausted. Completed chunks "
                    "are saved; do not resume with this provider until its quota "
                    "or credit limit resets."
                ) from error
            except Exception as error:
                record.update(
                    status="failed",
                    generated_context=None,
                    context_approx_tokens=0,
                    attempts=MAX_ATTEMPTS,
                    error=str(error),
                )
            append_record(record)
            latest[identifier] = record
            write_manifest(build_manifest(items, latest, source_hashes))

    final_manifest = build_manifest(items, latest, source_hashes)
    write_manifest(final_manifest)

    selected_chunks = [chunk for item in selected for chunk in item.chunks]
    selected_completed = sum(
        valid_success(latest.get(stable_chunk_id(chunk), {}), chunk)
        for chunk in selected_chunks
    )
    selected_unresolved = len(selected_chunks) - selected_completed
    print(
        f"Selected run: {selected_completed}/{len(selected_chunks)} completed; "
        f"{selected_unresolved} unresolved."
    )
    if selected_unresolved:
        raise SystemExit(
            f"Selected run remains partial: {selected_unresolved} unresolved chunks. "
            "Rerun the same command to resume."
        )
    if args.document:
        print("Pilot document complete; full corpus remains partial.")
    else:
        write_compact_chunks(items, latest)
        print("Full-corpus contextualization complete.")


if __name__ == "__main__":
    main()
