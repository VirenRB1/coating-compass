import os
from dataclasses import dataclass
from typing import Any

import truststore
from dotenv import load_dotenv
from langfuse import get_client

from src.config import (
    add_params_argument,
    get_params,
    load_params,
)

REQUIRED_LANGFUSE_VARIABLES = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
)


@dataclass(frozen=True)
class PromptVersion:
    """Application-facing snapshot of a versioned Langfuse text prompt."""

    name: str
    version: int
    label: str
    text: str
    config: dict[str, Any]


def validate_langfuse_environment() -> None:
    missing = [name for name in REQUIRED_LANGFUSE_VARIABLES if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing required Langfuse environment variables: " + ", ".join(missing)
        )


def fetch_baseline_prompt(client: Any | None = None) -> PromptVersion:
    """Fetch the prompt currently selected by the immutable baseline label."""

    get_params()
    load_dotenv()
    validate_langfuse_environment()

    if client is None:
        truststore.inject_into_ssl()
        client = get_client()

    prompt = client.get_prompt(
        get_params().prompt.name,
        label=get_params().prompt.label,
        type="text",
    )
    if not isinstance(prompt.prompt, str) or not prompt.prompt.strip():
        raise TypeError(
            f"Langfuse prompt {get_params().prompt.name!r} must be non-empty text."
        )

    return PromptVersion(
        name=prompt.name,
        version=prompt.version,
        label=get_params().prompt.label,
        text=prompt.prompt,
        config=dict(prompt.config or {}),
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect the configured Langfuse prompt."
    )
    add_params_argument(parser)
    load_params(parser.parse_args().params)
    prompt = fetch_baseline_prompt()
    print(f"Fetched prompt: {prompt.name}")
    print(f"Version: {prompt.version}")
    print(f"Label: {prompt.label}")
    print(f"Config: {prompt.config}")


if __name__ == "__main__":
    main()
