import json
import os
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


def _parse_response_to_json(response: Any) -> Tuple[Dict[str, Any], str]:
    """Extract JSON content and raw text from chat completions result."""
    raw_text = ""
    try:
        content = response.choices[0].message.content
        if isinstance(content, list):
            # Newer SDKs may return a list of content parts; join text parts.
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


def _call_model(system_prompt: str, user_prompt: str, response_format: Dict[str, Any], model: str) -> Tuple[Dict[str, Any], str]:
    load_dotenv()
    http_client = httpx.Client(trust_env=False)
    client = OpenAI(http_client=http_client)
    try:
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
    except OpenAIError as exc:
        raise RuntimeError(f"OpenAI call failed: {exc}") from exc
    return _parse_response_to_json(response)


def parse_with_llm(
    document_signal: List[Dict[str, Any]],
    category: str,
    model: str = os.getenv("OPENAI_MODEL", "gpt-5.2"),
    max_repairs: int = 2,
) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """
    Parse the document signal with the LLM and attempt auto-repair.

    Returns parsed_json, validation_errors, raw_outputs
    """
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(document_signal, category)

    raw_outputs: List[str] = []
    parsed, raw_text = _call_model(system_prompt, user_prompt, EXAM_SCHEMA, model=model)
    if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
        parsed["questions"] = [normalize_question_fields(q) for q in parsed.get("questions", [])]
    raw_outputs.append(raw_text)

    errors = validate_parsed_questions(parsed)
    attempts = 0
    while errors and attempts < max_repairs:
        attempts += 1
        repair_prompt = build_repair_prompt(parsed, errors)
        parsed, raw_text = _call_model(system_prompt, repair_prompt, EXAM_SCHEMA, model=model)
        if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
            parsed["questions"] = [normalize_question_fields(q) for q in parsed.get("questions", [])]
        raw_outputs.append(raw_text)
        errors = validate_parsed_questions(parsed)

    return parsed, errors, raw_outputs
