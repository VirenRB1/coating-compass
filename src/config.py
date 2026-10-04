"""Validated YAML settings shared by all entry points; no import-time I/O."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

ROOT = Path(__file__).resolve().parents[1]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Mode = Literal[
    "auto", "baseline-dense", "contextual-dense", "contextual-bm25", "contextual-hybrid"
]
Reasoning = Literal["minimal", "low", "medium", "high"]


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Paths(SettingsModel):
    sources: Path
    source_manifest: Path
    vector_store: Path
    contextual_artifacts: Path
    golden_requests: Path
    goldens: Path
    evaluation_results: Path
    reports: Path
    retriever_report: Path
    generator_report: Path

    @field_validator("*", mode="before")
    @classmethod
    def nonempty_path(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("path must not be empty")
        return value

    @field_serializer("*")
    def portable_path(self, value: Path):
        return value.as_posix()


class Chunking(SettingsModel):
    size: PositiveInt
    overlap: NonNegativeInt
    separators: tuple[str, ...]
    pdf_limit: PositiveInt | None

    @model_validator(mode="after")
    def check_overlap(self):
        if self.overlap >= self.size:
            raise ValueError("overlap must be smaller than chunk size")
        if not self.separators or self.separators[-1] != "":
            raise ValueError("separators must end with an empty-string fallback")
        return self


class Embeddings(SettingsModel):
    model: Text
    dimensions: PositiveInt
    timeout_seconds: PositiveFloat
    max_retries: NonNegativeInt
    contextual_batch_size: PositiveInt


class Generator(SettingsModel):
    provider: Literal["groq", "openai"]
    model: Text
    temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)]
    max_tokens: PositiveInt
    timeout_seconds: PositiveFloat
    max_retries: NonNegativeInt
    reasoning_effort: Reasoning | None

    def model_kwargs(self):
        values = self.model_dump(
            exclude={"provider", "timeout_seconds", "reasoning_effort"}
        )
        values["timeout"] = self.timeout_seconds
        if self.reasoning_effort is not None and self.model.startswith(
            ("openai/gpt-oss-", "gpt-5")
        ):
            values["reasoning_effort"] = self.reasoning_effort
        return values


class Retrieval(SettingsModel):
    mode: Mode
    k: PositiveInt
    search_type: Literal["similarity"]
    distance: Literal["Cosine", "Dot", "Euclid", "Manhattan"]
    baseline_collection: Text
    contextual_collection: Text
    bm25_name: Text
    bm25_k1: NonNegativeFloat
    bm25_b: Score
    hybrid_name: Text
    hybrid_dense_k: PositiveInt
    hybrid_bm25_k: PositiveInt
    hybrid_weights: tuple[Score, Score]
    hybrid_rrf_c: PositiveInt

    @model_validator(mode="after")
    def distinct_collections(self):
        if self.baseline_collection == self.contextual_collection:
            raise ValueError("baseline and contextual collections must be different")
        if abs(sum(self.hybrid_weights) - 1) > 1e-9 or any(
            weight <= 0 for weight in self.hybrid_weights
        ):
            raise ValueError("hybrid_weights must be positive and sum to one")
        return self


class Reranking(SettingsModel):
    enabled: bool
    model: Text
    requests_per_minute: PositiveFloat
    timeout_seconds: PositiveFloat


class Contextualization(SettingsModel):
    knowledge_base_version: Text
    provider: Literal["groq", "openai", "auto"]
    groq_model: Text
    openai_model: Text
    groq_temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)]
    openai_temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)] | None
    max_tokens: PositiveInt
    timeout_seconds: PositiveFloat
    max_retries: NonNegativeInt
    reasoning_effort: Reasoning
    max_attempts: PositiveInt
    retry_backoff_base: PositiveFloat
    retry_wait_margin_seconds: NonNegativeFloat
    requested_min_tokens: PositiveInt
    requested_max_tokens: PositiveInt
    min_context_tokens: PositiveInt
    max_context_tokens: PositiveInt
    document: Text | None

    @model_validator(mode="after")
    def token_bounds(self):
        if not (
            self.min_context_tokens
            <= self.requested_min_tokens
            <= self.requested_max_tokens
            <= self.max_context_tokens
        ):
            raise ValueError(
                "requested token range must lie inside accepted context token range"
            )
        return self


class GoldenGeneration(SettingsModel):
    model: Text
    temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)]
    max_tokens: PositiveInt
    reasoning_effort: Reasoning
    context_char_budget: Annotated[int, Field(ge=4000)]
    chunk_size: PositiveInt
    chunk_overlap: NonNegativeInt
    min_search_term_length: PositiveInt
    case_ids: tuple[Text, ...]

    @model_validator(mode="after")
    def check_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class Prompt(SettingsModel):
    name: Text
    label: Text
    registration_tags: tuple[Text, ...]


class Thresholds(SettingsModel):
    contextual_recall: Score
    contextual_precision: Score
    contextual_relevancy: Score
    answer_relevancy: Score
    faithfulness: Score
    answer_simplicity: Score
    answer_correctness: Score


class Evaluation(SettingsModel):
    judge_model: Text
    generator_judge_model: Text
    retriever_write_cache: bool
    retriever_use_cache: bool
    workers: PositiveInt
    comparison_workers: PositiveInt
    component_generator_workers: PositiveInt | None
    generator_rpm: PositiveFloat
    metric_timeout_seconds: Annotated[float, Field(ge=1, allow_inf_nan=False)]
    generation_attempts: PositiveInt
    generation_backoff_seconds: PositiveFloat
    case_ids: tuple[Text, ...]
    limit: PositiveInt | None
    component_label: Text
    comparison_label: Text
    comparison_modes: tuple[
        Literal["baseline-dense", "contextual-dense"],
        Literal["baseline-dense", "contextual-dense"],
    ]
    thresholds: Thresholds

    @model_validator(mode="after")
    def selection(self):
        if self.case_ids and self.limit is not None:
            raise ValueError("choose case_ids or limit, not both")
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("case_ids must be unique")
        if len(set(self.comparison_modes)) != 2:
            raise ValueError("comparison_modes must select both distinct dense modes")
        return self


class Params(SettingsModel):
    schema_version: Literal[1]
    paths: Paths
    chunking: Chunking
    embeddings: Embeddings
    generator: Generator
    retrieval: Retrieval
    reranking: Reranking
    contextualization: Contextualization
    golden_generation: GoldenGeneration
    prompt: Prompt
    evaluation: Evaluation

    @model_validator(mode="after")
    def reranking_requires_hybrid(self):
        if self.reranking.enabled and self.retrieval.mode != "contextual-hybrid":
            raise ValueError(
                "Cohere reranking requires retrieval.mode: contextual-hybrid"
            )
        return self


_params: Params | None = None


def load_params(filename: Path | str | None = None) -> Params:
    """Read YAML and validate every setting before activating it for this process."""
    global _params
    filename = Path(filename) if filename is not None else ROOT / "params.yaml"
    data = yaml.safe_load(filename.read_text(encoding="utf-8"))
    settings = Params.model_validate(data)
    _params = settings
    return settings


def get_params() -> Params:
    """Reuse the entry point's validated immutable settings, including in workers."""
    return _params if _params is not None else load_params()


def path(name: str) -> Path:
    paths = get_params().paths
    derived = {
        "contextual_manifest": paths.contextual_artifacts / "manifest.json",
        "contextual_records": paths.contextual_artifacts / "records",
        "contextual_chunks": paths.contextual_artifacts / "chunks.jsonl",
    }
    value = derived[name] if name in derived else getattr(paths, name)
    return value if value.is_absolute() else ROOT / value


def add_params_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--params",
        type=Path,
        help="YAML configuration (default: repository params.yaml)",
    )


def config_snapshot() -> dict:
    settings = get_params().model_dump(mode="json")
    encoded = json.dumps(
        settings, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return {
        "params": settings,
        "params_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
    }


def metric_threshold(name: str) -> float:
    return getattr(get_params().evaluation.thresholds, name.lower().replace(" ", "_"))


def validate_resume_config(run: dict) -> None:
    current = config_snapshot()
    if (
        run.get("params") != current["params"]
        or run.get("params_sha256") != current["params_sha256"]
    ):
        raise ValueError(
            "Cannot resume: validated configuration differs or the report has no configuration snapshot."
        )


def select_cases(goldens: list) -> list[tuple[int, dict]]:
    if not goldens:
        raise ValueError("Golden dataset must contain at least one case.")
    settings = get_params().evaluation
    indexed = list(enumerate(goldens, 1))
    selected = set(settings.case_ids)
    if selected:
        indexed = [(i, case) for i, case in indexed if f"manual_{i:03d}" in selected]
        missing = selected - {f"manual_{i:03d}" for i, _ in indexed}
        if missing:
            raise ValueError(f"Unknown case IDs: {sorted(missing)}")
    elif settings.limit is not None:
        indexed = indexed[: settings.limit]
    return indexed


def main():
    parser = argparse.ArgumentParser(
        description="Validate parameters offline and print the normalized snapshot."
    )
    add_params_argument(parser)
    args = parser.parse_args()
    load_params(args.params)
    print(json.dumps(config_snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
