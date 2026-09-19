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
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


SOURCE_DIRECTORY = Path("data/dulux_canada_knowledge_sources")
MANIFEST_PATH = SOURCE_DIRECTORY / "manifest.json"
VECTOR_STORE_DIRECTORY = Path("data/vector_store/qdrant")
COLLECTION_NAME = "coating-compass-baseline-v1"
EMBEDDING_DIMENSIONS = 1_536

CHUNK_SIZE = 1_000
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5


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


def load_manifest_metadata() -> dict[str, dict]:
    products = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    metadata_by_filename: dict[str, dict] = {}

    for product in products:
        for document_type in ("tds", "sds"):
            document = product[document_type]
            metadata_by_filename[document["filename"]] = {
                "product_family": product["product_family"],
                "sku": product["selected_sku"],
                "finish": product["selected_sheen"],
                "document_type": document_type.upper(),
                "document_sha256": document["sha256"],
                "source_url": product[f"{document_type}_url"],
            }

    return metadata_by_filename


def load_and_split_documents() -> list[Document]:
    metadata_by_filename = load_manifest_metadata()
    pages: list[Document] = []
    pdf_paths = sorted(SOURCE_DIRECTORY.glob("*.pdf"))
    pdf_limit = int(os.getenv("COATING_COMPASS_PDF_LIMIT", "0"))
    if pdf_limit > 0:
        pdf_paths = pdf_paths[:pdf_limit]

    for pdf_path in pdf_paths:
        source_metadata = metadata_by_filename[pdf_path.name]
        pdf = PdfReader(pdf_path)
        for page_index, pdf_page in enumerate(pdf.pages):
            pages.append(
                Document(
                    page_content=(pdf_page.extract_text() or "").strip(),
                    metadata={
                        **source_metadata,
                        "source_filename": pdf_path.name,
                        "page_number": page_index + 1,
                    },
                )
            )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(pages)


def chunk_id(document: Document, embedding_model: str) -> str:
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


def build_vector_store() -> QdrantVectorStore:
    embedding_model = os.getenv(
        "COATING_COMPASS_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    embeddings = OpenAIEmbeddingAdapter(model=embedding_model)
    VECTOR_STORE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(VECTOR_STORE_DIRECTORY))
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            ),
        )
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )

    chunks = load_and_split_documents()
    chunk_ids = [chunk_id(chunk, embedding_model) for chunk in chunks]
    existing_points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=chunk_ids,
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(point.id) for point in existing_points}

    missing_chunks = [
        chunk for chunk, identifier in zip(chunks, chunk_ids, strict=True)
        if identifier not in existing_ids
    ]
    missing_ids = [identifier for identifier in chunk_ids if identifier not in existing_ids]

    if missing_chunks:
        print(f"Embedding {len(missing_chunks)} new chunks...")
        vector_store.add_documents(documents=missing_chunks, ids=missing_ids)
    else:
        print(f"Reusing {len(chunk_ids)} existing chunk embeddings.")

    return vector_store


def create_rag_graph(vector_store: QdrantVectorStore):
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": RETRIEVAL_K},
    )
    model = ChatGroq(
        model=os.getenv("COATING_COMPASS_GROQ_MODEL", "openai/gpt-oss-20b"),
        temperature=0,
        max_tokens=700,
        timeout=30,
        max_retries=2,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an evidence-based coating assistant. Use only the supplied source "
                "excerpts. If the evidence is insufficient, say so. Do not invent product "
                "compatibility, preparation, coverage, drying, temperature, or safety claims. "
                "Include the supplied source filenames and page numbers in your answer. This is "
                "an unofficial decision-support prototype, not manufacturer-approved advice.",
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
    rag_graph = create_rag_graph(vector_store)

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
