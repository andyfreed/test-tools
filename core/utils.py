import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

ENCODING_WARNING = "Normalized text encoding artifacts"


def _append_warning(warnings: Optional[List[str]], message: str) -> None:
    if warnings is None:
        return
    if message not in warnings:
        warnings.append(message)


def _clean_mojibake(text: str) -> Tuple[str, bool]:
    """
    Fix common mojibake sequences that result from UTF-8 decoded as cp1252/latin-1.

    Uses ASCII fallbacks for safety.
    """
    replacements = {
        "ï¿½": "'",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "â€“": "-",
        "â€”": "-",
    }
    cleaned = text
    fixed = False
    for bad, good in replacements.items():
        if bad in cleaned:
            cleaned = cleaned.replace(bad, good)
            fixed = True
    return cleaned, fixed


def get_openai_client() -> OpenAI:
    """Return a configured OpenAI client or raise if the key is missing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return OpenAI(api_key=api_key)


def safe_json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def normalize_text(text: str, warnings: Optional[List[str]] = None) -> str:
    """Normalize text by flattening whitespace and newlines."""
    if not isinstance(text, str):
        return ""
    cleaned, fixed_mojibake = _clean_mojibake(text)
    if fixed_mojibake:
        _append_warning(warnings, ENCODING_WARNING)
    flattened = cleaned.replace("\n", " ")
    collapsed = re.sub(r"\s+", " ", flattened)
    return collapsed.strip()


def normalize_question_fields(q: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize title/options/warnings to avoid per-character iteration issues."""
    q = dict(q) if isinstance(q, dict) else {}
    q["title"] = normalize_text(q.get("title", ""))
    options = q.get("options", ["", "", "", ""])
    q["options"] = [normalize_text(opt) for opt in options]
    warnings_raw = q.get("warnings", []) or []
    if isinstance(warnings_raw, str):
        warnings_raw = [warnings_raw]
    normalized_warnings = [normalize_text(w) for w in warnings_raw]
    title = q.get("title", "")
    normalized_warnings = _filter_blank_year_warnings(title, normalized_warnings)
    q["warnings"] = normalized_warnings
    return q


def _filter_blank_year_warnings(title: str, warnings: List[str]) -> List[str]:
    """Keep 'blank year' warnings only when heuristics indicate a missing year."""
    if not warnings:
        return warnings
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", title or ""))
    has_in_punct = bool(re.search(r"\bin\s*[.,?]", title or "", flags=re.IGNORECASE))
    placeholder_patterns = [r"\bYYYY\b", r"\bYEAR\b", r"\[year\]", r"____"]
    has_placeholder = any(re.search(pat, title or "", flags=re.IGNORECASE) for pat in placeholder_patterns)

    def should_keep(w: str) -> bool:
        is_blank_year = "blank year" in (w or "").lower()
        if not is_blank_year:
            return True
        if has_year:
            return False
        return has_in_punct or has_placeholder

    return [w for w in warnings if should_keep(w)]


def index_to_letter(index: int) -> str:
    mapping = ["A", "B", "C", "D"]
    if index < 0 or index >= len(mapping):
        return "?"
    return mapping[index]


def letter_to_index(letter: str) -> Optional[int]:
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    return mapping.get(letter.upper().strip()) if letter else None


def normalize_questions_for_editor(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert parsed questions into rows usable by st.data_editor."""
    rows: List[Dict[str, Any]] = []
    for q in questions:
        q = normalize_question_fields(q)
        options = q.get("options", [""] * 4)
        warnings_raw = q.get("warnings", []) or []
        if isinstance(warnings_raw, str):
            warnings_raw = [warnings_raw]
        rows.append(
            {
                "number": q.get("number"),
                "title": q.get("title", ""),
                "option_A": options[0] if len(options) > 0 else "",
                "option_B": options[1] if len(options) > 1 else "",
                "option_C": options[2] if len(options) > 2 else "",
                "option_D": options[3] if len(options) > 3 else "",
                "correct_letter": index_to_letter(q.get("correct_index", 0)),
                "detected_answer_method": q.get("detected_answer_method", "inferred"),
                "warnings": " | ".join(warnings_raw),
                "delete": False,
            }
        )
    return rows


def editor_rows_to_questions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert edited rows back into the JSON structure expected by validation."""
    questions: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("delete"):
            continue
        options = [
            normalize_text(row.get("option_A", "") or ""),
            normalize_text(row.get("option_B", "") or ""),
            normalize_text(row.get("option_C", "") or ""),
            normalize_text(row.get("option_D", "") or ""),
        ]
        correct_index = letter_to_index(row.get("correct_letter") or "")
        questions.append(
            {
                "number": int(row.get("number") or 0),
                "title": normalize_text(row.get("title", "") or ""),
                "options": options,
                "correct_index": 0 if correct_index is None else correct_index,
                "detected_answer_method": row.get("detected_answer_method", "inferred"),
                "warnings": [
                    normalize_text(w)
                    for w in (row.get("warnings", "") or "").split("|")
                    if normalize_text(w)
                ],
                "source_refs": [],
            }
        )
    return questions
