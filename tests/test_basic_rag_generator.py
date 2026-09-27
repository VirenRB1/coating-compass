import unittest
from unittest.mock import patch

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from src.app.basic_rag import create_generator_model, generator_model_config


class GeneratorConfigurationTests(unittest.TestCase):
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
        ):
            with self.assertRaisesRegex(ValueError, "must be 'groq' or 'openai'"):
                generator_model_config()


if __name__ == "__main__":
    unittest.main()
