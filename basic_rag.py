import hashlib
import json
import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph


SOURCE_DIRECTORY = Path("data/dulux_canada_knowledge_sources")
MANIFEST_PATH = SOURCE_DIRECTORY / "manifest.json"
VECTOR_STORE_DIRECTORY = Path("data/vector_store")
COLLECTION_NAME = "coating-compass-baseline-v1"

CHUNK_SIZE = 1_000
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5


class RAGState(TypedDict):
    question: str
    documents: list[Document]
    answer: str


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

    for pdf_path in sorted(SOURCE_DIRECTORY.glob("*.pdf")):
        source_metadata = metadata_by_filename[pdf_path.name]
        loaded_pages = PyMuPDFLoader(str(pdf_path)).load()

        for page in loaded_pages:
            page.metadata.update(source_metadata)
            page.metadata["source_filename"] = pdf_path.name
            page.metadata["page_number"] = int(page.metadata.get("page", 0)) + 1
            pages.append(page)

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
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def build_vector_store() -> Chroma:
    embedding_model = os.getenv(
        "COATING_COMPASS_EMBEDDING_MODEL", "gemini-embedding-2"
    )
    embeddings = GoogleGenerativeAIEmbeddings(
        model=embedding_model,
        output_dimensionality=768,
    )
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_STORE_DIRECTORY),
        collection_metadata={"hnsw:space": "cosine"},
    )

    chunks = load_and_split_documents()
    chunk_ids = [chunk_id(chunk, embedding_model) for chunk in chunks]
    existing_ids = set(vector_store.get(ids=chunk_ids, include=[])["ids"])

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


def create_rag_graph(vector_store: Chroma):
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
    load_dotenv()
    vector_store = build_vector_store()
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
