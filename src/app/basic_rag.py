import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import TypedDict

import truststore
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.app.contextual_bm25 import (
    DEFAULT_B as BM25_B,
)
from src.app.contextual_bm25 import (
    DEFAULT_K1 as BM25_K1,
)
from src.app.contextual_bm25 import (
    ContextualBM25Retriever,
)
from src.app.evidence import render_retrieval_context
from src.app.prompt_registry import fetch_baseline_prompt
from src.data.contextualize_documents import (
    MANIFEST_PATH as CONTEXTUAL_MANIFEST_PATH,
)
from src.data.contextualize_documents import (
    PROMPT_HASH,
    read_latest_records,
    valid_success,
)
from src.data.corpus import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    load_document_chunks,
    stable_chunk_id,
)

VECTOR_STORE_DIRECTORY = Path("data/vector_store/qdrant")
BASELINE_COLLECTION_NAME = "coating-compass-baseline-v1"
CONTEXTUAL_COLLECTION_NAME = "coating-compass-contextual-dense-v1"
CONTEXTUAL_BM25_NAME = "coating-compass-contextual-bm25-v2"
RETRIEVAL_MODES = (
    "auto",
    "baseline-dense",
    "contextual-dense",
    "contextual-bm25",
)
DENSE_COLLECTIONS = {
    "baseline-dense": BASELINE_COLLECTION_NAME,
    "contextual-dense": CONTEXTUAL_COLLECTION_NAME,
}


def contextual_artifact_declares_complete() -> bool:
    if not CONTEXTUAL_MANIFEST_PATH.is_file():
        return False
    try:
        manifest = json.loads(CONTEXTUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return manifest.get("completion_state") == "complete"


COLLECTION_NAME = (
    CONTEXTUAL_COLLECTION_NAME
    if contextual_artifact_declares_complete()
    else BASELINE_COLLECTION_NAME
)
EMBEDDING_DIMENSIONS = 1_536

RETRIEVAL_K = 5
DEFAULT_GENERATOR_MAX_TOKENS = 2_000


class RAGState(TypedDict):
    question: str
    documents: list[Document]
    answer: str


def load_and_split_documents() -> list[Document]:
    chunks = load_document_chunks()
    pdf_limit = int(os.getenv("COATING_COMPASS_PDF_LIMIT", "0"))
    if pdf_limit > 0:
        filenames = sorted({chunk.metadata["source_filename"] for chunk in chunks})
        allowed = set(filenames[:pdf_limit])
        chunks = [
            chunk
            for chunk in chunks
            if chunk.metadata["source_filename"] in allowed
        ]
    return chunks


def chunk_id(document: Document, embedding_model: str) -> str:
    """Preserve the existing baseline point-ID format."""

    identity = "|".join(
        [
            document.metadata["document_sha256"],
            str(document.metadata["page_number"]),
            str(document.metadata.get("start_index", 0)),
            str(CHUNK_SIZE),
            str(CHUNK_OVERLAP),
            embedding_model,
            document.page_content,
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))


def contextual_retrieval_text(generated_context: str, original_text: str) -> str:
    """Compose embedding input without changing answer-generation evidence."""

    return f"{generated_context}\n\n{original_text}"


def generator_model_config() -> dict:
    """Return validated, reproducible settings for the hosted answer model."""

    provider = os.getenv("COATING_COMPASS_GENERATOR_PROVIDER", "groq").lower()
    if provider not in {"groq", "openai"}:
        raise ValueError(
            "COATING_COMPASS_GENERATOR_PROVIDER must be 'groq' or 'openai'."
        )
    default_model = (
        os.getenv("COATING_COMPASS_GROQ_MODEL", "openai/gpt-oss-20b")
        if provider == "groq"
        else "gpt-5-mini-2025-08-07"
    )
    model = os.getenv("COATING_COMPASS_GENERATOR_MODEL", default_model)
    max_tokens = int(
        os.getenv(
            "COATING_COMPASS_GENERATOR_MAX_TOKENS",
            str(DEFAULT_GENERATOR_MAX_TOKENS),
        )
    )
    if max_tokens < 1:
        raise ValueError("COATING_COMPASS_GENERATOR_MAX_TOKENS must be positive.")

    config = {
        "provider": provider,
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "timeout": 30,
        "max_retries": 2,
    }
    if model.startswith(("openai/gpt-oss-", "gpt-5")):
        config["reasoning_effort"] = os.getenv(
            "COATING_COMPASS_GENERATOR_REASONING_EFFORT", "low"
        )
    return config


def create_generator_model():
    """Construct the configured hosted chat model without changing RAG behavior."""

    config = generator_model_config()
    provider = config.pop("provider")
    if provider == "openai":
        return ChatOpenAI(**config)
    return ChatGroq(**config)


def load_complete_contextual_documents() -> list[tuple[str, Document, str]]:
    """Validate every contextual record before allowing any contextual indexing."""

    if not CONTEXTUAL_MANIFEST_PATH.is_file():
        raise ValueError(
            "Contextual artifacts are missing. Run "
            "`python -m src.data.contextualize_documents --dry-run` first."
        )
    manifest = json.loads(CONTEXTUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("completion_state") != "complete":
        raise ValueError("Contextual artifact manifest is not complete; refusing to index.")
    if manifest.get("context_settings", {}).get("prompt_sha256") != PROMPT_HASH:
        raise ValueError("Contextual artifact prompt hash is stale; refusing to index.")

    chunks = load_and_split_documents()
    current_source_hashes = {
        chunk.metadata["source_filename"]: chunk.metadata["document_sha256"]
        for chunk in chunks
    }
    if manifest.get("source_hashes") != current_source_hashes:
        raise ValueError("Contextual manifest source hashes are stale; refusing to index.")
    expected_counts = manifest.get("counts", {})
    document_count_changed = expected_counts.get("documents") != len(
        current_source_hashes
    )
    chunk_count_changed = expected_counts.get("chunks") != len(chunks)
    if document_count_changed or chunk_count_changed:
        raise ValueError("Contextual manifest counts do not match the current corpus.")
    latest = read_latest_records()
    expected_ids = {stable_chunk_id(chunk) for chunk in chunks}
    if set(latest) != expected_ids:
        raise ValueError("Contextual records do not exactly match current source chunks.")

    contextual_documents = []
    for chunk in chunks:
        identifier = stable_chunk_id(chunk)
        record = latest[identifier]
        if not valid_success(record, chunk):
            raise ValueError(f"Missing, invalid, or stale contextual record: {identifier}")
        metadata = {
            **chunk.metadata,
            "chunk_id": identifier,
            "generated_context": record["generated_context"],
            "generated_context_is_synthetic": True,
            "context_model": record["model"],
            "context_prompt_sha256": record["prompt_sha256"],
        }
        original = Document(page_content=chunk.page_content, metadata=metadata)
        retrieval_text = contextual_retrieval_text(
            record["generated_context"], chunk.page_content
        )
        contextual_documents.append((identifier, original, retrieval_text))
    return contextual_documents


def build_contextual_bm25_retriever() -> Runnable[str, list[Document]]:
    """Build a local lexical index from the complete contextual artifact."""

    # The loader returns (stable ID, original Document, context + original text).
    # BM25 indexes the last item but returns the original Document as evidence.
    return ContextualBM25Retriever(
        load_complete_contextual_documents(), k=RETRIEVAL_K
    )


def create_qdrant_store(
    client: QdrantClient, collection_name: str, embeddings: Embeddings
) -> QdrantVectorStore:
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            ),
        )
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )


def build_baseline_vector_store(
    client: QdrantClient, embeddings: Embeddings, embedding_model: str
) -> QdrantVectorStore:
    vector_store = create_qdrant_store(
        client, BASELINE_COLLECTION_NAME, embeddings
    )
    chunks = load_and_split_documents()
    identifiers = [chunk_id(chunk, embedding_model) for chunk in chunks]
    existing_points = client.retrieve(
        collection_name=BASELINE_COLLECTION_NAME,
        ids=identifiers,
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(point.id) for point in existing_points}
    missing_chunks = [
        chunk
        for chunk, identifier in zip(chunks, identifiers, strict=True)
        if identifier not in existing_ids
    ]
    missing_ids = [
        identifier for identifier in identifiers if identifier not in existing_ids
    ]
    if missing_chunks:
        print(f"Embedding {len(missing_chunks)} new baseline chunks...")
        vector_store.add_documents(documents=missing_chunks, ids=missing_ids)
    else:
        print(f"Reusing {len(identifiers)} existing baseline chunk embeddings.")
    return vector_store


def build_contextual_vector_store(
    client: QdrantClient, embeddings: Embeddings
) -> QdrantVectorStore:
    contextual_documents = load_complete_contextual_documents()
    vector_store = create_qdrant_store(
        client, CONTEXTUAL_COLLECTION_NAME, embeddings
    )
    chunk_ids = [item[0] for item in contextual_documents]
    existing_points = client.retrieve(
        collection_name=CONTEXTUAL_COLLECTION_NAME,
        ids=chunk_ids,
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(point.id) for point in existing_points}
    missing = [item for item in contextual_documents if item[0] not in existing_ids]
    if missing:
        print(f"Embedding {len(missing)} new contextual chunks...")
        for offset in range(0, len(missing), 64):
            batch = missing[offset : offset + 64]
            vectors = embeddings.embed_documents([item[2] for item in batch])
            client.upsert(
                collection_name=CONTEXTUAL_COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=identifier,
                        vector=vector,
                        payload={
                            "page_content": original.page_content,
                            "metadata": original.metadata,
                        },
                    )
                    for (identifier, original, _), vector in zip(
                        batch, vectors, strict=True
                    )
                ],
            )
    else:
        print(f"Reusing {len(chunk_ids)} existing contextual chunk embeddings.")
    return vector_store


def resolve_retrieval_mode(retrieval_mode: str) -> str:
    if retrieval_mode not in RETRIEVAL_MODES:
        raise ValueError(
            f"retrieval mode must be one of: {', '.join(RETRIEVAL_MODES)}."
        )
    if retrieval_mode == "auto":
        return (
            "contextual-dense"
            if contextual_artifact_declares_complete()
            else "baseline-dense"
        )
    return retrieval_mode


def retrieval_name(retrieval_mode: str) -> str:
    resolved = resolve_retrieval_mode(retrieval_mode)
    if resolved == "contextual-bm25":
        return CONTEXTUAL_BM25_NAME
    return DENSE_COLLECTIONS[resolved]


def retrieval_metadata(retrieval_mode: str) -> dict:
    resolved = resolve_retrieval_mode(retrieval_mode)
    is_bm25 = resolved == "contextual-bm25"
    return {
        "retrieval_mode": resolved,
        "retrieval_k": RETRIEVAL_K,
        # BM25 is rebuilt in memory; only dense modes have Qdrant collections.
        "collection": None if is_bm25 else DENSE_COLLECTIONS[resolved],
        "bm25_k1": BM25_K1 if is_bm25 else None,
        "bm25_b": BM25_B if is_bm25 else None,
        "bm25_implementation": "langchain-bm25okapi-v2" if is_bm25 else None,
    }


def build_vector_store(retrieval_mode: str = "auto") -> QdrantVectorStore:
    resolved = resolve_retrieval_mode(retrieval_mode)
    if resolved == "contextual-bm25":
        raise ValueError("contextual-bm25 does not use a vector store.")
    embedding_model = os.getenv(
        "COATING_COMPASS_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    embeddings = OpenAIEmbeddings(
        model=embedding_model, check_embedding_ctx_length=False,
        request_timeout=60, max_retries=2,
    )
    VECTOR_STORE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(VECTOR_STORE_DIRECTORY))
    if resolved == "contextual-dense":
        return build_contextual_vector_store(client, embeddings)
    return build_baseline_vector_store(client, embeddings, embedding_model)


def build_retriever(retrieval_mode: str = "auto"):
    """Return one object with the simple ``invoke(question)`` interface."""

    resolved = resolve_retrieval_mode(retrieval_mode)
    if resolved == "contextual-bm25":
        return build_contextual_bm25_retriever()

    # LangChain already provides the same invoke interface for Qdrant.
    return build_vector_store(resolved).as_retriever(
        search_type="similarity",
        search_kwargs={"k": RETRIEVAL_K},
    )


def create_rag_graph(retriever, system_prompt: str):
    """Create the smallest useful graph: retrieve evidence, then answer."""

    model = create_generator_model()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            (
                "human",
                ("Question:\n{question}\n\nRetrieved evidence:\n{context}\n\n"
                 "Return an answer, important limitations, and sources."),
            ),
        ]
    )

    def retrieve(state: RAGState) -> dict:
        # Both local BM25 and LangChain's dense retriever support invoke().
        documents = retriever.invoke(state["question"])
        return {"documents": documents}

    def generate(state: RAGState) -> dict:
        context_parts = render_retrieval_context(state["documents"])

        messages = prompt.invoke(
            {
                "question": state["question"],
                "context": "\n\n---\n\n".join(context_parts),
            }
        )
        response = model.invoke(messages)
        return {"answer": response.content}

    # The explicit two-node graph keeps retrieval and generation easy to test.
    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Coating Compass RAG app.")
    parser.add_argument(
        "--retrieval-mode",
        choices=RETRIEVAL_MODES,
        default="auto",
        help="Retrieval architecture (default: auto).",
    )
    args = parser.parse_args()
    truststore.inject_into_ssl()
    load_dotenv()
    retriever = build_retriever(args.retrieval_mode)
    if os.getenv("COATING_COMPASS_INGEST_ONLY") == "1":
        print("Ingest-only run complete.")
        return
    prompt_version = fetch_baseline_prompt()
    rag_graph = create_rag_graph(retriever, prompt_version.text)

    print(
        f"Coating Compass RAG is ready with {retrieval_name(args.retrieval_mode)}. "
        "Type 'quit' to exit."
    )
    while True:
        question = input("\nProject question: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            continue

        result = rag_graph.invoke({"question": question, "documents": [], "answer": ""})
        print(f"\n{result['answer']}")


if __name__ == "__main__":
    main()
