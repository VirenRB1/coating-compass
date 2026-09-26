"""Metric definitions for end-to-end Coating Compass evaluation.

The standard DeepEval metrics measure retrieval and grounded generation. The
two GEval metrics add project-specific judgments while keeping their rubrics
explicit and reviewable.
"""

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import SingleTurnParams


METRIC_NAMES = [
    "Contextual Recall",
    "Contextual Precision",
    "Contextual Relevancy",
    "Answer Relevancy",
    "Faithfulness",
    "Answer Simplicity",
    "Answer Correctness",
]


def build_full_pipeline_metrics(judge_model: str) -> list:
    """Return fresh metric instances for one test case.

    DeepEval metric objects retain the most recent score and reason, so callers
    should build a fresh suite for every independently persisted case.
    """

    return [
        ContextualRecallMetric(model=judge_model, async_mode=False),
        ContextualPrecisionMetric(model=judge_model, async_mode=False),
        ContextualRelevancyMetric(model=judge_model, async_mode=False),
        AnswerRelevancyMetric(model=judge_model, async_mode=False),
        FaithfulnessMetric(model=judge_model, async_mode=False),
        GEval(
            name="Answer Simplicity",
            _include_g_eval_suffix=False,
            model=judge_model,
            threshold=0.5,
            async_mode=False,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            evaluation_steps=[
                "Identify the information needed to answer the user's coating question.",
                "Check whether the answer is direct, clearly organized, and understandable to a non-specialist.",
                "Penalize repetition, unexplained jargon, and detail that does not help the user act safely.",
                "Do not reward brevity when it removes necessary limitations, warnings, conditions, or citations.",
                "Score overall simplicity from 0 to 1, where 1 is concise, clear, and complete enough for safe use.",
            ],
        ),
        GEval(
            name="Answer Correctness",
            _include_g_eval_suffix=False,
            model=judge_model,
            threshold=0.5,
            async_mode=False,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
            ],
            evaluation_steps=[
                "Extract the material coating claims, recommendation conditions, limitations, and safety guidance from the actual answer.",
                "Compare those claims with the expected answer and the retrieved manufacturer evidence.",
                "Penalize contradictions, unsupported product uses, incorrect preparation or primer decisions, missing critical qualifications, and unsafe advice.",
                "Allow wording and supported alternatives to differ from the expected answer; do not require exact string matching.",
                "Score correctness and completeness from 0 to 1, where 1 is fully correct, supported, and appropriately qualified.",
            ],
        ),
    ]
