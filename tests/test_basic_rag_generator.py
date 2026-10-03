import unittest
from unittest.mock import patch

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from src.app.basic_rag import (
    build_vector_store,
    create_generator_model,
    generator_model_config,
)


class GeneratorConfigurationTests(unittest.TestCase):
    def test_embeddings_delegate_without_automatic_token_splitting(self) -> None:
        with (
            patch("src.app.basic_rag.OpenAIEmbeddings") as embeddings,
            patch("src.app.basic_rag.VECTOR_STORE_DIRECTORY") as directory,
            patch("src.app.basic_rag.QdrantClient") as client,
            patch("src.app.basic_rag.build_baseline_vector_store") as build,
            patch.dict("os.environ", {"COATING_COMPASS_EMBEDDING_MODEL": "text-embedding-3-small"}),
        ):
            result = build_vector_store("baseline-dense")
        embeddings.assert_called_once_with(
            model="text-embedding-3-small", check_embedding_ctx_length=False,
            request_timeout=60, max_retries=2,
        )
        directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        build.assert_called_once_with(client.return_value, embeddings.return_value,
                                      "text-embedding-3-small")
        self.assertIs(result, build.return_value)

    def test_openai_generator_uses_gpt_5_mini(self) -> None:
        environment = {
            "OPENAI_API_KEY": "test-key",
            "COATING_COMPASS_GENERATOR_PROVIDER": "openai",
            "COATING_COMPASS_GENERATOR_MODEL": "gpt-5-mini-2025-08-07",
        }
        with patch.dict("os.environ", environment, clear=True):
            config = generator_model_config()
            model = create_generator_model()

        self.assertEqual(config["provider"], "openai")
        self.assertEqual(config["model"], "gpt-5-mini-2025-08-07")
        self.assertIsInstance(model, ChatOpenAI)

    def test_groq_remains_the_backward_compatible_default(self) -> None:
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=True):
            config = generator_model_config()
            model = create_generator_model()

        self.assertEqual(config["provider"], "groq")
        self.assertEqual(config["model"], "openai/gpt-oss-20b")
        self.assertIsInstance(model, ChatGroq)

    def test_unknown_generator_provider_fails_fast(self) -> None:
        with patch.dict(
            "os.environ", {"COATING_COMPASS_GENERATOR_PROVIDER": "unknown"}, clear=True
        ), self.assertRaisesRegex(ValueError, "must be 'groq' or 'openai'"):
            generator_model_config()


if __name__ == "__main__":
    unittest.main()
