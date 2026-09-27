"""JSON and Markdown artifact helpers for full-pipeline evaluations."""

import json
from pathlib import Path
from typing import Any

from .metrics import METRIC_NAMES


def calculate_averages(cases: list[dict[str, Any]]) -> dict[str, float]:
    """Calculate metric means across completed cases."""

    if not cases:
        return {}
    return {
        name: sum(case["metrics"][name]["score"] for case in cases) / len(cases)
        for name in METRIC_NAMES
    }


def write_json_report(output_path: Path, result: dict[str, Any]) -> None:
    """Persist the complete machine-readable evaluation result."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_markdown_report(output_path: Path, result: dict[str, Any]) -> None:
    """Persist a review-friendly summary beside the JSON artifact."""

    run = result["run"]
    cases = result["cases"]
    lines = [
        "# Full Pipeline Evaluation",
        "",
        "DeepEval scores use a 0-1 scale. GEval scores are model judgments and "
        "must be reviewed alongside their reasons and coating-domain checks.",
        "",
        "## Run metadata",
        "",
        f"- Label: `{run['label']}`",
        f"- Timestamp (UTC): `{run['timestamp_utc']}`",
        f"- Status: `{run['status']}`",
        f"- Collection: `{run['collection']}`",
        f"- Retrieval K: `{run['retrieval_k']}`",
        f"- Embedding model: `{run['embedding_model']}`",
        f"- Generator provider: `{run.get('generator_provider', 'groq')}`",
        f"- Generator model: `{run['generator_model']}`",
        f"- Generator max tokens: `{run.get('generator_max_tokens', 'not recorded')}`",
        f"- Generator reasoning effort: `{run.get('generator_reasoning_effort', 'not recorded')}`",
        f"- Judge model: `{run['judge_model']}`",
        f"- Golden dataset: `{run.get('goldens_path', 'not recorded')}`",
        f"- Parallel case workers: `{run['workers']}`",
        f"- Per-metric timeout: `{run['metric_timeout_seconds']} seconds`",
        f"- Golden dataset SHA-256: `{run['goldens_sha256']}`",
        "",
        "## Aggregate results",
        "",
        "| Metric | Average | Passed |",
        "|---|---:|---:|",
    ]
    for name in METRIC_NAMES:
        passed = sum(case["metrics"][name]["success"] for case in cases)
        average = result["averages"].get(name, 0.0)
        lines.append(f"| {name} | {average:.3f} | {passed}/{len(cases)} |")

    lines.extend(
        [
            "",
            "## Per-case results",
            "",
            "| Case | " + " | ".join(METRIC_NAMES) + " |",
            "|---|" + "---:|" * len(METRIC_NAMES),
        ]
    )
    for case in cases:
        scores = " | ".join(
            f"{case['metrics'][name]['score']:.3f}" for name in METRIC_NAMES
        )
        lines.append(f"| {case['case_id']} | {scores} |")

    lines.extend(["", "## Judge reasons", ""])
    for case in cases:
        lines.extend([f"### {case['case_id']}", "", f"**Question:** {case['question']}", ""])
        for name in METRIC_NAMES:
            metric = case["metrics"][name]
            reason = metric.get("reason") or metric.get("error") or "No reason returned."
            lines.append(
                f"- **{name} ({metric['score']:.3f}):** "
                f"{str(reason).replace(chr(10), ' ')}"
            )
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
