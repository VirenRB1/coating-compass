import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app.basic_rag import COLLECTION_NAME
from src.evals.application_evals.evaluate_full_pipeline import (
    GOLDENS_PATH,
    load_goldens,
    main,
    parse_args,
    validate_resume_generator,
    validate_resume_input,
)


VALID_GOLDENS = [
    {
        "question": "Which coating system is supported?",
        "expected_answer": "Use the documented preparation, primer, and topcoat.",
        "expected_context": ["Manufacturer passage with supporting evidence."],
    }
]


class FullPipelineInputTests(unittest.TestCase):
    def write_json(self, directory: str, name: str, value: object) -> Path:
        path = Path(directory, name)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_custom_golden_path_is_accepted_and_determines_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_json(directory, "reviewed.json", VALID_GOLDENS)
            expected_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            goldens, digest = load_goldens(path)
            with patch(
                "sys.argv", ["evaluate_full_pipeline", "--goldens", str(path)]
            ):
                args = parse_args()

        self.assertEqual(goldens, VALID_GOLDENS)
        self.assertEqual(digest, expected_digest)
        self.assertEqual(args.goldens, path)

    def test_default_path_remains_backward_compatible(self) -> None:
        with patch("sys.argv", ["evaluate_full_pipeline"]):
            args = parse_args()

        self.assertEqual(args.goldens, GOLDENS_PATH)
        self.assertIsNone(args.label)
        self.assertEqual(args.label or COLLECTION_NAME, COLLECTION_NAME)

    def test_malformed_dataset_fails_before_hosted_setup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_json(directory, "bad.json", [])
            with (
                patch(
                    "sys.argv", ["evaluate_full_pipeline", "--goldens", str(path)]
                ),
                patch(
                    "src.evals.application_evals.evaluate_full_pipeline.fetch_baseline_prompt"
                ) as fetch_prompt,
                patch(
                    "src.evals.application_evals.evaluate_full_pipeline.build_retriever"
                ) as build_retriever,
                self.assertRaises(ValueError),
            ):
                main()

        fetch_prompt.assert_not_called()
        build_retriever.assert_not_called()

    def test_changed_input_prevents_resume(self) -> None:
        saved = {"run": {"goldens_sha256": "original", "label": "collection-v1"}}
        with self.assertRaisesRegex(ValueError, "hash has changed"):
            validate_resume_input(
                saved, goldens_hash="changed", label="collection-v1"
            )

    def test_resume_rejects_a_different_generator(self) -> None:
        saved = {
            "run": {
                "generator_provider": "groq",
                "generator_model": "openai/gpt-oss-20b",
            }
        }
        with self.assertRaisesRegex(ValueError, "generator provider or model"):
            validate_resume_generator(
                saved, provider="openai", model="gpt-5-mini-2025-08-07"
            )


if __name__ == "__main__":
    unittest.main()
