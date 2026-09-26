import os

import truststore
from dotenv import load_dotenv
from langfuse import get_client

PROMPT_NAME = "coating_compass_baseline_prompt"

SYSTEM_PROMPT = """You are an evidence-based coating assistant. Use only the supplied source excerpts. If the evidence is insufficient, say so. Do not invent product compatibility, preparation, coverage, drying, temperature, or safety claims. Include the supplied source filenames and page numbers in your answer. This is an unofficial decision-support prototype, not manufacturer-approved advice."""

def validate_environment() -> None:
    required_variables = [
          "LANGFUSE_PUBLIC_KEY",
          "LANGFUSE_SECRET_KEY",
          "LANGFUSE_BASE_URL",
    ]

    missing = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing:
        missing_names = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variables:{missing_names}"
        )
def main() -> None:
    truststore.inject_into_ssl()
    load_dotenv()
    validate_environment()

    langfuse = get_client()

    prompt = langfuse.create_prompt(
        name=PROMPT_NAME,
        type="text",
        prompt=SYSTEM_PROMPT,
        labels=["baseline"],
        tags=["rag", "system-prompt"],
        config={
            "description": "Baseline system prompt from the first complete RAG evaluation",
            "generation_model": "openai/gpt-oss-20b",
            "temperature": 0,
            "retrieval": {
                "chunk_size": 1000,
                "chunk_overlap": 150,
                "top_k": 5,
                "search_type": "similarity",
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


