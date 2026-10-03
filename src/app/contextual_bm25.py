"""Dependency-free BM25 retrieval over contextualized manufacturer chunks."""

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def tokenize(text: str) -> list[str]:
    """Normalize text into deterministic, case-insensitive lexical terms."""

    return _TOKEN_PATTERN.findall(text.lower())


@dataclass(frozen=True)
class _IndexedDocument:
    """Everything BM25 needs for one chunk after startup."""

    chunk_id: str
    original_document: object
    term_frequencies: Counter[str]
    length: int


class ContextualBM25Retriever:
    """Rank original chunks using BM25 over context + original chunk text.

    Each input contains a stable ID, the original evidence document, and separate
    retrieval text. Search results always return the original evidence document.
    """

    def __init__(
        self,
        contextual_documents: Iterable[tuple[str, object, str]],
        *,
        k: int = 5,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        if k < 1:
            raise ValueError("k must be positive.")
        if k1 < 0:
            raise ValueError("k1 must be non-negative.")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1.")

        indexed: list[_IndexedDocument] = []
        document_frequencies: Counter[str] = Counter()
        for chunk_id, original_document, retrieval_text in contextual_documents:
            if not chunk_id:
                raise ValueError("chunk_id must not be empty.")
            terms = tokenize(retrieval_text)
            if not terms:
                raise ValueError("Retrieval text must contain a searchable term.")
            frequencies = Counter(terms)
            indexed.append(
                _IndexedDocument(
                    chunk_id, original_document, frequencies, len(terms)
                )
            )
            # Count a term once per document. BM25 uses this to reward rare terms.
            document_frequencies.update(frequencies.keys())
        if not indexed:
            raise ValueError("At least one contextual document is required.")

        # These corpus statistics never change, so calculate them only once.
        self._documents = indexed
        self._average_length = sum(item.length for item in indexed) / len(indexed)
        self._idf = {
            term: math.log(
                1 + (len(indexed) - frequency + 0.5) / (frequency + 0.5)
            )
            for term, frequency in document_frequencies.items()
        }
        self.k = k
        self.k1 = k1
        self.b = b

    def invoke(self, query: str) -> list[object]:
        """Return up to ``k`` original chunks with a positive lexical score."""

        # Repeating a word in the question should not artificially boost it.
        query_terms = set(tokenize(query))
        ranked: list[tuple[float, str, object]] = []
        for item in self._documents:
            length_ratio = item.length / self._average_length
            score = 0.0
            for term in query_terms:
                term_frequency = item.term_frequencies.get(term, 0)
                if not term_frequency:
                    continue
                # Standard BM25: k1 limits repeated-term gains; b normalizes length.
                denominator = term_frequency + self.k1 * (
                    1 - self.b + self.b * length_ratio
                )
                score += (
                    self._idf[term]
                    * term_frequency
                    * (self.k1 + 1)
                    / denominator
                )
            if score > 0:
                ranked.append((score, item.chunk_id, item.original_document))

        # Stable IDs make ties reproducible even if corpus input order changes.
        ranked.sort(key=lambda result: (-result[0], result[1]))
        return [document for _, _, document in ranked[: self.k]]
