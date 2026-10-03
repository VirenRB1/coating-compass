import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.app.basic_rag import create_rag_graph, retrieval_metadata
from src.app.contextual_bm25 import ContextualBM25Retriever
from src.app.evidence import render_retrieval_context
from src.evals.application_evals.evaluate_full_pipeline import validate_resume_retrieval


class EvidenceBoundaryTests(unittest.TestCase):
    def test_synthetic_context_retrieves_but_never_reaches_generator(self):
        original = Document(
            page_content="Original manufacturer warning.",
            metadata={"source_filename": "tds.pdf", "page_number": 2,
                      "document_sha256": "hash", "source_url": "https://example.com/tds",
                      "generated_context": "syntheticneedle fabricated claim"},
        )
        retriever = ContextualBM25Retriever([
            ("chunk", original, "syntheticneedle fabricated claim\n\n" + original.page_content)
        ])
        prompts = []

        def answer(prompt):
            prompts.append(prompt.to_string())
            return AIMessage(content="Supported answer.")

        with patch("src.app.basic_rag.create_generator_model", return_value=RunnableLambda(answer)):
            graph = create_rag_graph(retriever, "Use manufacturer evidence only.")
            result = graph.invoke({"question": "syntheticneedle", "documents": [], "answer": ""})

        self.assertIs(result["documents"][0], original)
        self.assertIn("Source: tds.pdf, page 2\nOriginal manufacturer warning.", prompts[0])
        self.assertNotIn("fabricated claim", prompts[0])
        self.assertEqual(render_retrieval_context(result["documents"]),
                         ["Source: tds.pdf, page 2\nOriginal manufacturer warning."])

    def test_old_bm25_run_cannot_resume_with_new_scoring(self):
        config = retrieval_metadata("contextual-bm25")
        old = {key: value for key, value in config.items() if key != "bm25_implementation"}
        with self.assertRaisesRegex(ValueError, "bm25_implementation"):
            validate_resume_retrieval({"run": old}, retrieval_config=config)
        validate_resume_retrieval({"run": config}, retrieval_config=config)


if __name__ == "__main__":
    unittest.main()
