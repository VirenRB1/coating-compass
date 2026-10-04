import argparse
import hashlib
import json
import uuid
from typing import TypedDict

import truststore
from dotenv import load_dotenv
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.app.contextual_bm25 import ContextualBM25Retriever
from src.app.evidence import render_retrieval_context
from src.app.prompt_registry import fetch_baseline_prompt
from src.app.reranking import build_reranking_retriever, cohere_api_key
from src.config import (
    add_params_argument,
    get_params,
    load_params,
)
from src.config import path as config_path
from src.data.contextualize_documents import (
    prompt_hash,
    read_latest_records,
    valid_success,
)
from src.data.corpus import (
    load_document_chunks,
    stable_chunk_id,
)

RETRIEVAL_MODES = (
    "auto",
    "baseline-dense",
    "contextual-dense",
    "contextual-bm25",
    "contextual-hybrid",
)


def contextual_artifact_declares_complete() -> bool:
    if not config_path("contextual_manifest").is_file():
        return False
    try:
        manifest = json.loads(
            config_path("contextual_manifest").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False
    return manifest.get("completion_state") == "complete"


class RAGState(TypedDict):
    question: str
    documents: list[Document]
    answer: str


def load_and_split_documents() -> list[Document]:
    chunks = load_document_chunks()
    pdf_limit = get_params().chunking.pdf_limit
    if pdf_limit is not None:
        filenames = sorted({chunk.metadata["source_filename"] for chunk in chunks})
        allowed = set(filenames[:pdf_limit])
        chunks = [
            chunk for chunk in chunks if chunk.metadata["source_filename"] in allowed
        ]
    return chunks


def chunk_id(document: Document, embedding_model: str) -> str:
    """Preserve the existing baseline point-ID format."""

    identity = "|".join(
        [
            document.metadata["document_sha256"],
            str(document.metadata["page_number"]),
            str(document.metadata.get("start_index", 0)),
            str(get_params().chunking.size),
            str(get_params().chunking.overlap),
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
    settings = get_params().generator
    return {"provider": settings.provider, **settings.model_kwargs()}


def create_generator_model():
    """Construct the configured hosted chat model without changing RAG behavior."""

    config = generator_model_config()
    provider = config.pop("provider")
    if provider == "openai":
        return ChatOpenAI(**config)
    return ChatGroq(**config)


def load_complete_contextual_documents() -> list[tuple[str, Document, str]]:
    """Validate every contextual record before allowing any contextual indexing."""

    if not config_path("contextual_manifest").is_file():
        raise ValueError(
            "Contextual artifacts are missing. Run "
            "`python -m src.data.contextualize_documents --dry-run` first."
        )
    manifest = json.loads(
        config_path("contextual_manifest").read_text(encoding="utf-8")
    )
    if manifest.get("completion_state") != "complete":
        raise ValueError(
            "Contextual artifact manifest is not complete; refusing to index."
        )
    if (
        manifest.get("knowledge_base_version")
        != get_params().contextualization.knowledge_base_version
    ):
        raise ValueError(
            "Contextual knowledge-base version differs from configuration."
        )
    if manifest.get("chunk_settings") != {
        "size": get_params().chunking.size,
        "overlap": get_params().chunking.overlap,
    }:
        raise ValueError("Contextual chunk settings differ from configuration.")
    if manifest.get("context_settings", {}).get("prompt_sha256") != prompt_hash():
        raise ValueError("Contextual artifact prompt hash is stale; refusing to index.")

    chunks = load_and_split_documents()
    current_source_hashes = {
        chunk.metadata["source_filename"]: chunk.metadata["document_sha256"]
        for chunk in chunks
    }
    if manifest.get("source_hashes") != current_source_hashes:
        raise ValueError(
            "Contextual manifest source hashes are stale; refusing to index."
        )
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
        raise ValueError(
            "Contextual records do not exactly match current source chunks."
        )

    contextual_documents = []
    for chunk in chunks:
        identifier = stable_chunk_id(chunk)
        record = latest[identifier]
        if not valid_success(record, chunk):
            raise ValueError(
                f"Missing, invalid, or stale contextual record: {identifier}"
            )
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
        load_complete_contextual_documents(), k=get_params().retrieval.k
    )


def create_qdrant_store(
    client: QdrantClient,
    collection_name: str,
    embeddings: Embeddings,
    *,
    contextual_inputs_sha256: str | None = None,
) -> QdrantVectorStore:
    settings = get_params()
    identity = {
        "embedding_model": settings.embeddings.model,
        "dimensions": settings.embeddings.dimensions,
        "distance": settings.retrieval.distance,
        "chunking": settings.chunking.model_dump(mode="json"),
    }
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=get_params().embeddings.dimensions,
                distance=Distance(get_params().retrieval.distance),
            ),
            metadata={"coating_compass_index": identity},
        )
    info = client.get_collection(collection_name)
    vectors = info.config.params.vectors
    if (
        vectors.size != get_params().embeddings.dimensions
        or vectors.distance != Distance(get_params().retrieval.distance)
    ):
        raise ValueError(
            "Existing collection dimensions/distance do not match configured embeddings."
        )
    recorded = (info.config.metadata or {}).get("coating_compass_index")
    if recorded is None and info.points_count:
        # Immutable identity of the two indexes built before YAML configuration.
        # These are migration facts, not fallback run settings.
        legacy = {
            "embedding_model": "text-embedding-3-small",
            "dimensions": 1536,
            "distance": "Cosine",
            "chunking": {
                "size": 1000,
                "overlap": 150,
                "separators": ["\n\n", "\n", ". ", " ", ""],
                "pdf_limit": None,
            },
        }
        if (
            collection_name
            not in {
                "coating-compass-baseline-v1",
                "coating-compass-contextual-dense-v1",
            }
            or identity != legacy
        ):
            raise ValueError(
                "Unversioned existing index cannot be reused with these settings. Choose a new collection name."
            )
    elif recorded is not None and recorded != identity:
        raise ValueError(
            "Index model/chunking configuration changed. Choose a new collection name."
        )
    if recorded is None:
        client.update_collection(
            collection_name, metadata={"coating_compass_index": identity}
        )
    if contextual_inputs_sha256 is not None:
        recorded_inputs = (info.config.metadata or {}).get("contextual_inputs_sha256")
        if recorded_inputs is not None and recorded_inputs != contextual_inputs_sha256:
            raise ValueError(
                "Contextual embedding inputs changed. Choose a new collection name."
            )
        if recorded_inputs is None:
            client.update_collection(
                collection_name,
                metadata={"contextual_inputs_sha256": contextual_inputs_sha256},
            )
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        distance=Distance(settings.retrieval.distance),
        # Dimensions and distance were checked locally above; avoid LangChain's
        # hosted dummy embedding request when validating an existing collection.
        validate_collection_config=False,
    )


def build_baseline_vector_store(
    client: QdrantClient, embeddings: Embeddings, embedding_model: str
) -> QdrantVectorStore:
    vector_store = create_qdrant_store(
        client, get_params().retrieval.baseline_collection, embeddings
    )
    chunks = load_and_split_documents()
    identifiers = [chunk_id(chunk, embedding_model) for chunk in chunks]
    existing_points = client.retrieve(
        collection_name=get_params().retrieval.baseline_collection,
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
    client: QdrantClient,
    embeddings: Embeddings,
    contextual_documents: list[tuple[str, Document, str]] | None = None,
) -> QdrantVectorStore:
    if contextual_documents is None:
        contextual_documents = load_complete_contextual_documents()
    vector_store = create_qdrant_store(
        client,
        get_params().retrieval.contextual_collection,
        embeddings,
        contextual_inputs_sha256=hashlib.sha256(
            json.dumps(
                [(identifier, text) for identifier, _, text in contextual_documents],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    )
    chunk_ids = [item[0] for item in contextual_documents]
    existing_points = client.retrieve(
        collection_name=get_params().retrieval.contextual_collection,
        ids=chunk_ids,
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(point.id) for point in existing_points}
    missing = [item for item in contextual_documents if item[0] not in existing_ids]
    if missing:
        print(f"Embedding {len(missing)} new contextual chunks...")
        for offset in range(
            0, len(missing), get_params().embeddings.contextual_batch_size
        ):
            batch = missing[
                offset : offset + get_params().embeddings.contextual_batch_size
            ]
            vectors = embeddings.embed_documents([item[2] for item in batch])
            client.upsert(
                collection_name=get_params().retrieval.contextual_collection,
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
    retrieval_mode = (
        get_params().retrieval.mode if retrieval_mode is None else retrieval_mode
    )
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


def dense_collection(mode: str) -> str:
    settings = get_params().retrieval
    return (
        settings.contextual_collection
        if mode in {"contextual-dense", "contextual-hybrid"}
        else settings.baseline_collection
    )


def retrieval_name(retrieval_mode: str) -> str:
    resolved = resolve_retrieval_mode(retrieval_mode)
    if resolved == "contextual-bm25":
        return get_params().retrieval.bm25_name
    if resolved == "contextual-hybrid":
        name = get_params().retrieval.hybrid_name
        return f"{name}-cohere" if get_params().reranking.enabled else name
    return dense_collection(resolved)


def retrieval_metadata(retrieval_mode: str) -> dict:
    resolved = resolve_retrieval_mode(retrieval_mode)
    is_bm25 = resolved == "contextual-bm25"
    is_hybrid = resolved == "contextual-hybrid"
    settings = get_params().retrieval
    return {
        "retrieval_mode": resolved,
        "retrieval_k": get_params().retrieval.k,
        # BM25 is rebuilt in memory; only dense modes have Qdrant collections.
        "collection": None if is_bm25 else dense_collection(resolved),
        "bm25_k1": settings.bm25_k1 if is_bm25 or is_hybrid else None,
        "bm25_b": settings.bm25_b if is_bm25 or is_hybrid else None,
        "bm25_implementation": "langchain-bm25okapi-v2"
        if is_bm25 or is_hybrid
        else None,
        "hybrid_implementation": "langchain-ensemble-rrf-v1" if is_hybrid else None,
        "hybrid_dense_k": settings.hybrid_dense_k if is_hybrid else None,
        "hybrid_bm25_k": settings.hybrid_bm25_k if is_hybrid else None,
        "hybrid_weights": list(settings.hybrid_weights) if is_hybrid else None,
        "hybrid_rrf_c": settings.hybrid_rrf_c if is_hybrid else None,
        "reranking_model": get_params().reranking.model
        if is_hybrid and get_params().reranking.enabled
        else None,
        "reranking_implementation": "langchain-cohere-rerank-v1"
        if is_hybrid and get_params().reranking.enabled
        else None,
    }


def build_vector_store(
    retrieval_mode: str | None = None, *, contextual_documents=None
) -> QdrantVectorStore:
    resolved = resolve_retrieval_mode(retrieval_mode)
    if resolved == "contextual-bm25":
        raise ValueError("contextual-bm25 does not use a vector store.")
    settings = get_params().embeddings
    embedding_model = settings.model
    embeddings = OpenAIEmbeddings(
        model=embedding_model,
        check_embedding_ctx_length=False,
        request_timeout=settings.timeout_seconds,
        max_retries=settings.max_retries,
        dimensions=settings.dimensions,
    )
    config_path("vector_store").mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(config_path("vector_store")))
    try:
        if resolved in {"contextual-dense", "contextual-hybrid"}:
            return build_contextual_vector_store(
                client, embeddings, contextual_documents
            )
        return build_baseline_vector_store(client, embeddings, embedding_model)
    except Exception:
        client.close()
        raise


def build_retriever(retrieval_mode: str | None = None):
    """Return one object with the simple ``invoke(question)`` interface."""

    resolved = resolve_retrieval_mode(retrieval_mode)
    if get_params().reranking.enabled and resolved != "contextual-hybrid":
        raise ValueError("Cohere reranking is supported only for contextual-hybrid.")
    if resolved == "contextual-bm25":
        return build_contextual_bm25_retriever()
    if resolved == "contextual-hybrid":
        settings = get_params().retrieval
        # Validate Cohere credentials before opening Qdrant or embedding anything.
        if get_params().reranking.enabled:
            cohere_api_key()
        documents = load_complete_contextual_documents()
        lexical = ContextualBM25Retriever(documents, k=settings.hybrid_bm25_k)
        dense = build_vector_store(
            "contextual-dense", contextual_documents=documents
        ).as_retriever(
            search_type=settings.search_type,
            search_kwargs={"k": settings.hybrid_dense_k},
        )
        # Rank fusion avoids comparing incomparable dense and BM25 scores.
        # Both branches return original chunks; identity preserves page citations.
        ensemble = EnsembleRetriever(
            retrievers=[dense, lexical],
            weights=list(settings.hybrid_weights),
            c=settings.hybrid_rrf_c,
            id_key="chunk_id",
        )
        if get_params().reranking.enabled:
            try:
                return build_reranking_retriever(ensemble)
            except Exception:
                dense.vectorstore.client.close()
                raise
        return ensemble | RunnableLambda(lambda documents: documents[: settings.k])

    # LangChain already provides the same invoke interface for Qdrant.
    return build_vector_store(resolved).as_retriever(
        search_type=get_params().retrieval.search_type,
        search_kwargs={"k": get_params().retrieval.k},
    )


def create_rag_graph(retriever, system_prompt: str, *, rate_limiter=None):
    """Create the smallest useful graph: retrieve evidence, then answer."""

    model = create_generator_model()
    if rate_limiter is not None:
        model.rate_limiter = rate_limiter
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            (
                "human",
                (
                    "Question:\n{question}\n\nRetrieved evidence:\n{context}\n\n"
                    "Return an answer, important limitations, and sources."
                ),
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
    add_params_argument(parser)
    parser.add_argument("--ingest-only", action="store_true")
    args = parser.parse_args()
    settings = load_params(args.params)
    args.retrieval_mode = settings.retrieval.mode
    truststore.inject_into_ssl()
    load_dotenv()
    retriever = build_retriever(args.retrieval_mode)
    if args.ingest_only:
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
