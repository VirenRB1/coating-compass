"""LangChain BM25 with an original-manufacturer-evidence boundary."""

import math
import re
from collections.abc import Iterable

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableLambda

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def tokenize(text: str) -> list[str]:
    """Keep case-insensitive product numbers and punctuation-separated terms."""
    return re.findall(r"\w+", text.lower())


def ContextualBM25Retriever(
    contextual_documents: Iterable[tuple[str, Document, str]],
    *,
    k: int = 5,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> Runnable[str, list[Document]]:
    """Compose maintained ranking with overlap filtering and original-only output.

    Rank all candidates before filtering: BM25Okapi can assign zero or negative
    scores to matching terms in small corpora. Overlap excludes unrelated chunks.
    """
    if k < 1:
        raise ValueError("k must be positive.")
    if not math.isfinite(k1) or k1 < 0:
        raise ValueError("k1 must be finite and non-negative.")
    if not math.isfinite(b) or not 0 <= b <= 1:
        raise ValueError("b must be between 0 and 1.")

    originals: dict[str, Document] = {}
    terms: dict[str, set[str]] = {}
    indexed = []
    for chunk_id, original, retrieval_text in sorted(
        contextual_documents, key=lambda item: item[0]
    ):
        if not chunk_id or chunk_id in originals:
            raise ValueError("chunk_id must be non-empty and unique.")
        tokens = set(tokenize(retrieval_text))
        if not tokens:
            raise ValueError("Retrieval text must contain a searchable term.")
        originals[chunk_id] = original
        terms[chunk_id] = tokens
        indexed.append(
            Document(page_content=retrieval_text, metadata={"chunk_id": chunk_id})
        )
    if not indexed:
        raise ValueError("At least one contextual document is required.")

    ranker = BM25Retriever.from_documents(
        indexed, k=len(indexed), preprocess_func=tokenize,
        bm25_params={"k1": k1, "b": b},
    )

    def original_evidence(result: dict) -> list[Document]:
        query_terms = set(tokenize(result["query"]))
        return [
            originals[document.metadata["chunk_id"]]
            for document in result["ranked"]
            if query_terms & terms[document.metadata["chunk_id"]]
        ][:k]

    # Runnable composition propagates LangChain callbacks/config to the ranker.
    return {
        "query": RunnableLambda(lambda query: query), "ranked": ranker,
    } | RunnableLambda(original_evidence)
