import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

SOURCE_DIRECTORY = Path("data/dulux_canada_knowledge_sources")
DEFAULT_REQUESTS_PATH = Path("data/evaluations/golden_generation_requests.json")
DEFAULT_OUTPUT_PATH = Path("data/evaluations/manual_golden_dataset.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate expert-reviewable RAG goldens from selected local PDFs."
    )
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--case-id",
        action="append",
        help="Generate only this case ID. Repeat to select multiple cases.",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Call the configured hosted model. Without this flag, only validate inputs.",
    )
    parser.add_argument(
        "--context-char-budget",
        type=int,
        default=16_000,
        help="Maximum extracted source characters sent for each case.",
    )
    return parser.parse_args()


def load_requests(path: Path) -> list[dict[str, Any]]:
    requests_data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(requests_data, list):
        raise ValueError("The generation request file must contain a JSON list.")
    case_ids = [request.get("case_id") for request in requests_data]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Generation request case IDs must be unique.")
    return requests_data


def has_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return "<" in value or ">" in value
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return False


def validate_request(request: dict[str, Any]) -> list[Path]:
    required = ("case_id", "question", "pdf_filenames", "answer_guidance")
    missing = [field for field in required if not request.get(field)]
    if missing:
        raise ValueError(f"{request.get('case_id', '<unknown>')}: missing {missing}")
    if has_placeholder([request["question"], request["pdf_filenames"], request["answer_guidance"]]):
        raise ValueError(f"{request['case_id']}: replace all angle-bracket placeholders")

    pdf_paths = [SOURCE_DIRECTORY / filename for filename in request["pdf_filenames"]]
    missing_pdfs = [str(path) for path in pdf_paths if not path.is_file()]
    if missing_pdfs:
        raise ValueError(f"{request['case_id']}: PDFs not found: {missing_pdfs}")
    return pdf_paths


def search_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 4
    }


def relevance_score(text: str, terms: set[str]) -> int:
    lowered = text.lower()
    return sum(1 + lowered.count(term) for term in terms if term in lowered)


def extract_relevant_pdf_text(
    pdf_paths: list[Path], query: str, char_budget: int
) -> str:
    if char_budget < 4_000:
        raise ValueError("The context character budget must be at least 4000.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1_800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    terms = search_terms(query)
    candidates: list[dict[str, Any]] = []
    for pdf_path in pdf_paths:
        reader = PdfReader(pdf_path)
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            for chunk_number, chunk in enumerate(splitter.split_text(text), start=1):
                rendered = (
                    f"SOURCE: {pdf_path.name}\n"
                    f"PAGE: {page_number}\n"
                    f"EXCERPT: {chunk_number}\n{chunk}"
                )
                candidates.append(
                    {
                        "source": pdf_path.name,
                        "key": (pdf_path.name, page_number, chunk_number),
                        "score": relevance_score(chunk, terms),
                        "text": rendered,
                    }
                )

    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, int, int]] = set()
    used_chars = 0

    # Guarantee at least one excerpt from every document selected by the owner.
    for pdf_path in pdf_paths:
        source_candidates = [
            item for item in candidates if item["source"] == pdf_path.name
        ]
        best = max(source_candidates, key=lambda item: item["score"])
        selected.append(best)
        selected_keys.add(best["key"])
        used_chars += len(best["text"]) + 7

    # Fill the remaining budget with the strongest excerpts across all documents.
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        if candidate["key"] in selected_keys:
            continue
        added_chars = len(candidate["text"]) + 7
        if used_chars + added_chars > char_budget:
            continue
        selected.append(candidate)
        selected_keys.add(candidate["key"])
        used_chars += added_chars

    return "\n\n---\n\n".join(item["text"] for item in selected)


def parse_json_response(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        raise ValueError("The model returned non-text content.")
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
    result = json.loads(cleaned)
    if not isinstance(result.get("expected_answer"), str):
        raise ValueError("Model response is missing a string expected_answer.")
    if not isinstance(result.get("expected_context"), list) or not all(
        isinstance(item, str) for item in result["expected_context"]
    ):
        raise ValueError("Model response is missing a string-list expected_context.")
    return result


def generate_golden(
    request: dict[str, Any],
    pdf_paths: list[Path],
    model: BaseChatModel,
    context_char_budget: int,
) -> dict[str, Any]:
    source_text = extract_relevant_pdf_text(
        pdf_paths,
        query=f"{request['question']}\n{request['answer_guidance']}",
        char_budget=context_char_budget,
    )
    print(
        f"{request['case_id']}: sending {len(source_text):,} source characters "
        f"from {len(pdf_paths)} document(s)."
    )
    messages = [
        SystemMessage(
            content=(
                "You create human-reviewable golden cases for a coating RAG system. "
                "Use only the supplied manufacturer text. Return one JSON object with "
                "exactly two keys: expected_context, a list of the shortest verbatim source "
                "passages sufficient to answer the question; and expected_answer, a concise "
                "answer supported by those passages. Preserve limitations, conditions, units, "
                "and warnings. Every material conclusion in expected_answer must be directly "
                "supported by at least one expected_context passage. When rejecting a product, "
                "include the passage that establishes its intended use or exclusion; do not use "
                "an edition line or other bibliographic text as evidence. If the sources do not "
                "support an answer, say that explicitly. "
                "Do not wrap the JSON in Markdown."
            )
        ),
        HumanMessage(
            content=(
                f"QUESTION:\n{request['question']}\n\n"
                f"ANSWER GUIDANCE:\n{request['answer_guidance']}\n\n"
                f"MANUFACTURER SOURCES:\n{source_text}"
            )
        ),
    ]
    response = model.invoke(messages)
    usage = response.usage_metadata or {}
    if usage:
        print(
            f"{request['case_id']}: token usage "
            f"input={usage.get('input_tokens', 'unknown')}, "
            f"output={usage.get('output_tokens', 'unknown')}, "
            f"total={usage.get('total_tokens', 'unknown')}."
        )
    generated = parse_json_response(response.content)
    return {
        "question": request["question"],
        "expected_context": generated["expected_context"],
        "expected_answer": generated["expected_answer"],
        "retrieved_context": [],
        "actual_answer": None,
    }


def main() -> None:
    args = parse_args()
    requests_data = load_requests(args.requests)
    selected_ids = set(args.case_id or [])
    selected = [
        request
        for request in requests_data
        if not selected_ids or request.get("case_id") in selected_ids
    ]
    if selected_ids - {request.get("case_id") for request in selected}:
        missing = sorted(selected_ids - {request.get("case_id") for request in selected})
        raise ValueError(f"Unknown case IDs: {missing}")

    validated: list[tuple[dict[str, Any], list[Path]]] = []
    errors: list[str] = []
    for request in selected:
        try:
            validated.append((request, validate_request(request)))
        except ValueError as error:
            errors.append(str(error))

    if errors:
        raise ValueError("Generation requests are not ready:\n- " + "\n- ".join(errors))

    print(f"Validated {len(validated)} generation request(s).")
    if not args.generate:
        print("Dry run complete. Add --generate to call the hosted model.")
        return

    load_dotenv()
    model_name = os.getenv(
        "COATING_COMPASS_GOLDEN_MODEL", "gpt-5-mini-2025-08-07"
    )
    print(f"Generating with OpenAI model {model_name}.")
    model = ChatOpenAI(
        model=model_name,
        temperature=0,
        max_tokens=4_000,
        reasoning_effort="minimal",
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    generated_goldens = [
        generate_golden(
            request,
            pdf_paths,
            model,
            context_char_budget=args.context_char_budget,
        )
        for request, pdf_paths in validated
    ]
    existing_goldens: list[dict[str, Any]] = []
    if args.output.is_file():
        existing_goldens = json.loads(args.output.read_text(encoding="utf-8"))
        if not isinstance(existing_goldens, list):
            raise ValueError("The existing golden output must contain a JSON list.")
    generated_questions = {golden["question"] for golden in generated_goldens}
    goldens = [
        golden
        for golden in existing_goldens
        if golden.get("question") not in generated_questions
    ]
    goldens.extend(generated_goldens)
    request_order = {
        request["question"]: index for index, request in enumerate(requests_data)
    }
    goldens.sort(
        key=lambda golden: request_order.get(
            golden.get("question", ""), len(request_order)
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(goldens, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {len(generated_goldens)} draft golden(s); "
        f"the output now contains {len(goldens)} case(s) at {args.output}."
    )


if __name__ == "__main__":
    main()
