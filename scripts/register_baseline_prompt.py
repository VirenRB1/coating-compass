import os

import truststore
from dotenv import load_dotenv
from langfuse import get_client

from src.config import (
    add_params_argument,
    get_params,
    load_params,
)

SYSTEM_PROMPT = """You are an evidence-based coating assistant. Use only the supplied source excerpts. If the evidence is insufficient, say so. Do not invent product compatibility, preparation, coverage, drying, temperature, or safety claims. Include the supplied source filenames and page numbers in your answer. This is an unofficial decision-support prototype, not manufacturer-approved advice."""


def validate_environment() -> None:
    required_variables = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
    ]

    missing = [variable for variable in required_variables if not os.getenv(variable)]

    if missing:
        missing_names = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables:{missing_names}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Register the configured baseline prompt."
    )
    add_params_argument(parser)
    load_params(parser.parse_args().params)
    truststore.inject_into_ssl()
    load_dotenv()
    validate_environment()

    langfuse = get_client()

    prompt = langfuse.create_prompt(
        name=get_params().prompt.name,
        type="text",
        prompt=SYSTEM_PROMPT,
        labels=[get_params().prompt.label],
        tags=list(get_params().prompt.registration_tags),
        config={
            "description": "Baseline system prompt from the first complete RAG evaluation",
            "generation_model": get_params().generator.model,
            "temperature": get_params().generator.temperature,
            "retrieval": {
                "chunk_size": get_params().chunking.size,
                "chunk_overlap": get_params().chunking.overlap,
                "top_k": get_params().retrieval.k,
                "search_type": get_params().retrieval.search_type,
            },
        },
        commit_message="Register prompt used for initial RAG evaluation",
    )

    print(f"Created prompt: {prompt.name}")
    print(f"Version: {prompt.version}")
    print(f"Labels: {prompt.labels}")
    print(f"Config: {prompt.config}")


if __name__ == "__main__":
    main()
