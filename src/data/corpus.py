"""Deterministic extraction and chunking for the local manufacturer corpus."""

import hashlib
import json
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


SOURCE_DIRECTORY = Path("data/dulux_canada_knowledge_sources")
MANIFEST_PATH = SOURCE_DIRECTORY / "manifest.json"
CHUNK_SIZE = 1_000
CHUNK_OVERLAP = 150


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def source_paths(document: str | None = None) -> list[Path]:
    paths = sorted(SOURCE_DIRECTORY.glob("*.pdf"))
    if document is None:
        return paths
    selected = [path for path in paths if path.name == document]
    if not selected:
        raise ValueError(f"Document is not in the source corpus: {document}")
    return selected


def extract_pages(pdf_path: Path, metadata: dict) -> list[Document]:
    actual_hash = file_sha256(pdf_path)
    expected_hash = metadata["document_sha256"]
    if actual_hash != expected_hash:
        raise ValueError(
            f"Source hash mismatch for {pdf_path.name}: expected {expected_hash}, "
            f"found {actual_hash}."
        )
    reader = PdfReader(pdf_path)
    return [
        Document(
            page_content=(page.extract_text() or "").strip(),
            metadata={
                **metadata,
                "source_filename": pdf_path.name,
                "page_number": index + 1,
            },
        )
        for index, page in enumerate(reader.pages)
    ]


def split_pages(pages: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(pages)


def load_document_chunks(document: str | None = None) -> list[Document]:
    metadata = load_manifest_metadata()
    chunks: list[Document] = []
    for path in source_paths(document):
        chunks.extend(split_pages(extract_pages(path, metadata[path.name])))
    return chunks


def stable_chunk_id(document: Document) -> str:
    """Return an ID tied to immutable source/chunk inputs, not an embedding model."""

    identity = "|".join(
        [
            document.metadata["document_sha256"],
            str(document.metadata["page_number"]),
            str(document.metadata.get("start_index", 0)),
            str(CHUNK_SIZE),
            str(CHUNK_OVERLAP),
            document.page_content,
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return str(uuid.UUID(digest[:32]))


def render_full_document(pages: list[Document]) -> str:
    return "\n\n".join(
        f"<page number=\"{page.metadata['page_number']}\">\n"
        f"{page.page_content}\n</page>"
        for page in pages
    )
