import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from src.app.basic_rag import (
    build_contextual_bm25_retriever,
    resolve_retrieval_mode,
    retrieval_metadata,
    retrieval_name,
)
from src.app.contextual_bm25 import (
    ContextualBM25Retriever,
    tokenize,
)


class ContextualBM25RetrieverTests(unittest.TestCase):
    def test_explicit_retrieval_modes_have_stable_names(self) -> None:
        self.assertEqual(resolve_retrieval_mode("baseline-dense"), "baseline-dense")
        self.assertEqual(
            retrieval_name("contextual-dense"),
            "coating-compass-contextual-dense-v1",
        )
        self.assertEqual(
            retrieval_name("contextual-bm25"),
            "coating-compass-contextual-bm25-v2",
        )

    def test_unknown_retrieval_mode_fails_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "retrieval mode must be one of"):
            resolve_retrieval_mode("unknown")

    def test_bm25_metadata_has_settings_but_no_qdrant_collection(self) -> None:
        self.assertEqual(
            retrieval_metadata("contextual-bm25"),
            {
                "retrieval_mode": "contextual-bm25",
                "retrieval_k": 5,
                "collection": None,
                "bm25_k1": 1.5,
                "bm25_b": 0.75,
                "bm25_implementation": "langchain-bm25okapi-v2",
            },
        )

    def test_generated_context_can_make_original_chunk_retrievable(self) -> None:
        alkyd = Document(
            page_content="Recommended for doors, trim, cabinets and walls.",
            metadata={"source_filename": "xpert-22010-tds.pdf", "page_number": 1},
        )
        floor = Document(
            page_content="Provides excellent abrasion resistance.",
            metadata={"source_filename": "floor-enamel-tds.pdf", "page_number": 1},
        )
        retriever = ContextualBM25Retriever(
            [
                (
                    "alkyd-id",
                    alkyd,
                    "Dulux X-PERT Waterborne Alkyd 22010 melamine finish.",
                ),
                (
                    "floor-id",
                    floor,
                    "Dulux Water-based Floor Enamel for concrete and wood floors.",
                ),
            ],
            k=1,
        )

        results = retriever.invoke("22010")

        self.assertEqual(results, [alkyd])
        self.assertNotIn("Waterborne Alkyd", results[0].page_content)

    def test_original_manufacturer_text_is_also_indexed(self) -> None:
        cabinet_chunk = Document(page_content="Use on cabinets and doors.")
        wall_chunk = Document(page_content="Use on interior drywall.")
        retriever = ContextualBM25Retriever(
            [
                (
                    "cabinet-id",
                    cabinet_chunk,
                    "Alkyd coating.\n\nUse on cabinets and doors.",
                ),
                (
                    "wall-id",
                    wall_chunk,
                    "Latex coating.\n\nUse on interior drywall.",
                ),
            ],
            k=1,
        )

        self.assertEqual(retriever.invoke("cabinets"), [cabinet_chunk])

    def test_unknown_terms_return_no_unsupported_evidence(self) -> None:
        retriever = ContextualBM25Retriever(
            [
                (
                    "wall-id",
                    Document(page_content="Interior wall coating."),
                    "Dulux paint.",
                )
            ]
        )

        self.assertEqual(retriever.invoke("submarine antifouling"), [])

    def test_builder_accepts_existing_contextual_record_shape(self) -> None:
        metadata = {
            "chunk_id": "stable-id",
            "document_sha256": "source-hash",
            "source_filename": "manufacturer-tds.pdf",
            "page_number": 2,
            "source_url": "https://example.com/manufacturer-tds.pdf",
        }
        document = Document(
            page_content="Manufacturer evidence.", metadata=metadata
        )

        retriever = ContextualBM25Retriever(
            [("stable-id", document, "Generated context.\n\nManufacturer evidence.")]
        )

        result = retriever.invoke("generated")

        self.assertEqual(result, [document])
        self.assertEqual(result[0].metadata, metadata)

    def test_tokenization_is_case_insensitive_and_keeps_product_numbers(self) -> None:
        self.assertEqual(tokenize("X-PERT 22010/01"), ["x", "pert", "22010", "01"])

    def test_ties_are_reproducible_across_input_order(self) -> None:
        chunk_b = Document(page_content="Second by stable ID.")
        chunk_a = Document(page_content="First by stable ID.")
        retriever = ContextualBM25Retriever(
            [
                ("chunk-b", chunk_b, "shared term"),
                ("chunk-a", chunk_a, "shared term"),
            ]
        )

        reverse = ContextualBM25Retriever(
            [("chunk-a", chunk_a, "shared term"), ("chunk-b", chunk_b, "shared term")]
        )
        self.assertCountEqual(retriever.invoke("shared"), [chunk_a, chunk_b])
        self.assertEqual(retriever.invoke("shared"), reverse.invoke("shared"))

    def test_invalid_configuration_fails_fast(self) -> None:
        corpus = [
            ("chunk-id", Document(page_content="Evidence."), "Context evidence.")
        ]

        with self.assertRaisesRegex(ValueError, "k must be positive"):
            ContextualBM25Retriever(corpus, k=0)
        with self.assertRaisesRegex(ValueError, "At least one"):
            ContextualBM25Retriever([])
        with self.assertRaisesRegex(ValueError, "searchable term"):
            ContextualBM25Retriever(
                [("chunk-id", Document(page_content="Evidence."), "---")]
            )

    def test_duplicate_ids_cannot_replace_original_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            ContextualBM25Retriever([
                ("same", Document(page_content="First source."), "context"),
                ("same", Document(page_content="Different source."), "context"),
            ])

    def test_filtering_happens_before_top_k_even_with_negative_scores(self) -> None:
        matching = Document(page_content="Original matching source.")
        unrelated = Document(page_content="Unrelated source.")
        retriever = ContextualBM25Retriever([
            ("a", matching, "common"),
            ("b", matching, "common"),
            ("c", unrelated, "unrelated"),
        ], k=1)
        self.assertEqual(retriever.invoke("common"), [matching])
        self.assertEqual(retriever.invoke("---"), [])

    def test_builder_validates_artifacts_before_constructing_ranker(self) -> None:
        with (
            patch("src.app.basic_rag.load_complete_contextual_documents",
                  side_effect=ValueError("stale artifact")),
            patch("src.app.contextual_bm25.BM25Retriever.from_documents") as ranker,
            self.assertRaisesRegex(ValueError, "stale artifact"),
        ):
            build_contextual_bm25_retriever()
        ranker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
