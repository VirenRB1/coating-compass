import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import TypedDict

import requests
import truststore
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import END, START, StateGraph
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.app.prompt_registry import fetch_baseline_prompt
from src.data.contextualize_documents import (
    MANIFEST_PATH as CONTEXTUAL_MANIFEST_PATH,
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


class OpenAIEmbeddingAdapter(Embeddings):
    """Expose OpenAI embeddings through LangChain's embedding interface."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.api_key = os.environ["OPENAI_API_KEY"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]


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

    model = os.getenv("COATING_COMPASS_GROQ_MODEL", "openai/gpt-oss-20b")
    max_tokens = int(
        os.getenv(
            "COATING_COMPASS_GENERATOR_MAX_TOKENS",
            str(DEFAULT_GENERATOR_MAX_TOKENS),
        )
    )
    if max_tokens < 1:
        raise ValueError("COATING_COMPASS_GENERATOR_MAX_TOKENS must be positive.")

    config = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "timeout": 30,
        "max_retries": 2,
    }
    if model.startswith("openai/gpt-oss-"):
        config["reasoning_effort"] = os.getenv(
            "COATING_COMPASS_GENERATOR_REASONING_EFFORT", "low"
        )
    return config


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


def create_qdrant_store(
    client: QdrantClient, collection_name: str, embeddings: OpenAIEmbeddingAdapter
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
    client: QdrantClient, embeddings: OpenAIEmbeddingAdapter, embedding_model: str
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
    client: QdrantClient, embeddings: OpenAIEmbeddingAdapter
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


def build_vector_store() -> QdrantVectorStore:
    embedding_model = os.getenv(
        "COATING_COMPASS_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    embeddings = OpenAIEmbeddingAdapter(model=embedding_model)
    VECTOR_STORE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(VECTOR_STORE_DIRECTORY))
    if contextual_artifact_declares_complete():
        return build_contextual_vector_store(client, embeddings)
    return build_baseline_vector_store(client, embeddings, embedding_model)


def create_rag_graph(vector_store: QdrantVectorStore, system_prompt: str):
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": RETRIEVAL_K},
    )
    model = ChatGroq(**generator_model_config())
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt,
            ),
            (
                "human",
                "Question:\n{question}\n\nRetrieved evidence:\n{context}\n\n"
                "Return an answer, important limitations, and sources.",
            ),
        ]
    )

    def retrieve(state: RAGState) -> dict:
        documents = retriever.invoke(state["question"])
        return {"documents": documents}

    def generate(state: RAGState) -> dict:
        context_parts = []
        for document in state["documents"]:
            source = document.metadata["source_filename"]
            page = document.metadata["page_number"]
            context_parts.append(f"Source: {source}, page {page}\n{document.page_content}")

        messages = prompt.invoke(
            {
                "question": state["question"],
                "context": "\n\n---\n\n".join(context_parts),
            }
        )
        response = model.invoke(messages)
        return {"answer": response.content}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def main() -> None:
    truststore.inject_into_ssl()
    load_dotenv()
    vector_store = build_vector_store()
    if os.getenv("COATING_COMPASS_INGEST_ONLY") == "1":
        print("Ingest-only run complete.")
        return
    prompt_version = fetch_baseline_prompt()
    rag_graph = create_rag_graph(vector_store, prompt_version.text)

    print("Coating Compass basic RAG is ready. Type 'quit' to exit.")
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
