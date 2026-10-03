"""Shared citation rendering for application prompts and evaluation evidence."""

from langchain_core.documents import Document


def render_retrieval_context(documents: list[Document]) -> list[str]:
    """Render original page text; synthetic retrieval metadata is never evidence."""
    return [
        f"Source: {document.metadata['source_filename']}, "
        f"page {document.metadata['page_number']}\n{document.page_content}"
        for document in documents
    ]
