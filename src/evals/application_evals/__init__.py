"""End-to-end DeepEval evaluation for the complete RAG pipeline."""

from .metrics import METRIC_NAMES, build_full_pipeline_metrics

__all__ = ["METRIC_NAMES", "build_full_pipeline_metrics"]
