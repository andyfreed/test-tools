import json
import os
import re
from typing import Any, Dict, List, Tuple

import httpx
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from .prompts import build_repair_prompt, build_system_prompt, build_user_prompt
from .utils import normalize_question_fields, safe_json_dumps
from .validate import validate_parsed_questions

SCHEMA_NAME = "exam_questions_v1"
EXAM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["category", "questions"],
    "properties": {
        "category": {"type": "string"},
        "questions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "number",
                    "title",
                    "options",
                    "correct_index",
                    "detected_answer_method",
                    "confidence",
                    "warnings",
                    "source_refs",
                ],
                "properties": {
                    "number": {"type": "integer", "minimum": 1},
                    "title": {"type": "string", "minLength": 1},
                    "options": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "detected_answer_method": {
                        "type": "string",
                        "enum": ["asterisk", "highlight", "answer_key", "inferred"],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "warnings": {"type": "array", "items": {"type": "string"}},
                    "source_refs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["kind", "index"],
                            "properties": {
                                "kind": {"type": "string", "enum": ["paragraph", "line"]},
                                "index": {"type": "integer", "minimum": 0},
                            },
                        },
                    },
                },
            },
        },
    },
}

RESPONSES_API_MODELS = {"gpt-5.4-pro", "gpt-5.4"}
CHUNK_SIZE = 30

# ---------------------------------------------------------------------------
# Patterns for chunking (mirrors extract.py to avoid circular imports)
# ---------------------------------------------------------------------------
_Q_START_PATTERNS = [
    re.compile(r"^\s*(\d{1,4})[.)]\s+\S"),
    re.compile(r"^\s*Q(\d{1,4})[:.)]\s+\S", flags=re.IGNORECASE),
    re.compile(r"^\s*\[[^\]]*p\d+[^\]]*\]", flags=re.IGNORECASE),
]
_AK_PATTERN = re.compile(
    r"^\s*(?:Q\s*)?(\d{1,4})\s*[.)]?\s*[:=\-]?\s*([A-D])\b", flags=re.IGNORECASE
)
_AK_ANNOTATION_RE = re.compile(r"\s*\[[^\]]+\]\s*$")


def _is_question_start(text: str) -> bool:
    return any(p.match(text) for p in _Q_START_PATTERNS)


def _is_answer_key_entry(text: str) -> bool:
    cleaned = re.sub(_AK_ANNOTATION_RE, "", text or "")
    return bool(_AK_PATTERN.match(cleaned))


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response_to_json(response: Any) -> Tuple[Dict[str, Any], str]:
    """Extract JSON content and raw text from chat completions result."""
    raw_text = ""
    try:
        content = response.choices[0].message.content
        if isinstance(content, list):
            raw_text = "".join([c.get("text", "") for c in content if isinstance(c, dict)])
        else:
            raw_text = content or ""
    except Exception:
        raw_text = ""
    parsed: Dict[str, Any] = {}
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = {}
    return parsed, raw_text


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------

def _call_model(system_prompt: str, user_prompt: str, response_format: Dict[str, Any], model: str) -> Tuple[Dict[str, Any], str]:
    load_dotenv()
    http_client = httpx.Client(trust_env=False)
    client = OpenAI(http_client=http_client)
    try:
        if model in RESPONSES_API_MODELS:
            response = client.responses.create(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": SCHEMA_NAME,
                        "strict": True,
                        "schema": response_format,
                    }
                },
            )
            raw_text = response.output_text or ""
            parsed: Dict[str, Any] = {}
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed = {}
            return parsed, raw_text
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": SCHEMA_NAME,
                        "strict": True,
                        "schema": response_format,
                    },
                },
            )
            return _parse_response_to_json(response)
    except OpenAIError as exc:
        raise RuntimeError(f"OpenAI call failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Chunking — split large documents so the LLM processes ~CHUNK_SIZE questions
# at a time, with the answer key included in every chunk.
# ---------------------------------------------------------------------------

def _items_key(signal: Dict[str, Any]) -> str:
    """Return 'paragraphs' or 'lines' depending on content type."""
    return "paragraphs" if "paragraphs" in signal else "lines"


def _find_answer_key_section(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect consecutive answer-key entries from the end of the item list."""
    answer_items: List[Dict[str, Any]] = []
    for item in reversed(items):
        if _is_answer_key_entry(item.get("text", "")):
            answer_items.insert(0, item)
        elif answer_items:
            break
    return answer_items


def _chunk_signals(
    signals: List[Dict[str, Any]], chunk_size: int = CHUNK_SIZE
) -> List[List[Dict[str, Any]]]:
    """Split signals into chunks if they contain more than *chunk_size* questions."""
    total_q = sum(
        (sig.get("debug_counts", {}).get("question_starts", 0) or 0)
        for sig in signals
    )
    if total_q <= chunk_size:
        return [signals]

    chunks: List[List[Dict[str, Any]]] = []
    for sig in signals:
        key = _items_key(sig)
        items = sig.get(key, [])

        # Find question-start positions
        q_starts = [
            i for i, item in enumerate(items)
            if _is_question_start(item.get("text", ""))
        ]

        if len(q_starts) <= chunk_size:
            chunks.append([sig])
            continue

        # Identify the answer-key block so we can append it to every chunk
        answer_key = _find_answer_key_section(items)
        ak_indices = {item.get("i") for item in answer_key}

        for g in range(0, len(q_starts), chunk_size):
            start = q_starts[g]
            end = (
                q_starts[g + chunk_size]
                if g + chunk_size < len(q_starts)
                else len(items)
            )
            # Take question items, skip any answer-key lines already captured
            chunk_items = [
                dict(it) for it in items[start:end]
                if it.get("i") not in ak_indices
            ]
            # Append the full answer key
            chunk_items.extend(dict(ak) for ak in answer_key)

            # Re-index so the LLM sees sequential indices
            for new_i, ci in enumerate(chunk_items):
                ci["i"] = new_i
                ci["line_index"] = new_i

            chunk_sig = dict(sig)
            chunk_sig[key] = chunk_items
            chunks.append([chunk_sig])

    return chunks if chunks else [signals]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_with_llm(
    document_signal: List[Dict[str, Any]],
    category: str,
    model: str = os.getenv("OPENAI_MODEL", "gpt-5.4"),
    max_repairs: int = 2,
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Parse the document signal with the LLM, chunking large documents and
    attempting auto-repair on each chunk.

    Returns (parsed_json, validation_errors, raw_outputs).
    """
    system_prompt = build_system_prompt()
    chunks = _chunk_signals(document_signal)

    all_questions: List[Dict[str, Any]] = []
    all_raw_outputs: List[str] = []

    for chunk in chunks:
        user_prompt = build_user_prompt(chunk, category)
        parsed, raw_text = _call_model(system_prompt, user_prompt, EXAM_SCHEMA, model=model)
        if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
            parsed["questions"] = [normalize_question_fields(q) for q in parsed["questions"]]
        all_raw_outputs.append(raw_text)

        errors = validate_parsed_questions(parsed)
        attempts = 0
        while errors and attempts < max_repairs:
            attempts += 1
            repair_prompt = build_repair_prompt(parsed, errors, document_signal=chunk)
            parsed, raw_text = _call_model(system_prompt, repair_prompt, EXAM_SCHEMA, model=model)
            if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
                parsed["questions"] = [normalize_question_fields(q) for q in parsed["questions"]]
            all_raw_outputs.append(raw_text)
            errors = validate_parsed_questions(parsed)

        if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
            all_questions.extend(parsed["questions"])

    # Renumber questions sequentially across all chunks
    for i, q in enumerate(all_questions, start=1):
        q["number"] = i

    merged: Dict[str, Any] = {"category": category, "questions": all_questions}
    final_errors = validate_parsed_questions(merged)
    return merged, final_errors, all_raw_outputs
