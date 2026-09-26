import os
import unittest
from unittest.mock import patch

from src.app.basic_rag import generator_model_config


class GeneratorModelConfigTests(unittest.TestCase):
    def test_gpt_oss_defaults_to_larger_budget_and_low_reasoning(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = generator_model_config()

        self.assertEqual(config["model"], "openai/gpt-oss-20b")
        self.assertEqual(config["max_tokens"], 2_000)
        self.assertEqual(config["reasoning_effort"], "low")

    def test_non_gpt_oss_model_omits_reasoning_effort(self) -> None:
        with patch.dict(
            os.environ,
            {"COATING_COMPASS_GROQ_MODEL": "example/non-reasoning-model"},
            clear=True,
        ):
            config = generator_model_config()

        self.assertNotIn("reasoning_effort", config)

    def test_token_budget_must_be_positive(self) -> None:
        with patch.dict(
            os.environ,
            {"COATING_COMPASS_GENERATOR_MAX_TOKENS": "0"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "must be positive"):
                generator_model_config()


if __name__ == "__main__":
    unittest.main()
