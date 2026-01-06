from typing import Any, Dict, List

from .utils import safe_json_dumps


def build_system_prompt() -> str:
    return (
        "You are an assistant that converts exam documents into structured JSON. "
        "Use only the provided document signal. Do not invent content. "
        "Every question must have exactly four options in A/B/C/D order and a single correct answer. "
        "Detect correct answers using asterisks, highlight, or an answer key. "
        "If unsure, set detected_answer_method to inferred and pick the best guess."
    )


def build_user_prompt(document_signal: List[Dict[str, Any]], category: str) -> str:
    guidance = (
        "Document signal is a faithful extraction of the source. "
        "Rules:\n"
        "- Asterisks (*) or (**) surrounding or preceding/following an option mean that option is correct; strip asterisks in output.\n"
        "- In DOCX, any option paragraph with highlight marks the correct answer.\n"
        "- Answer keys at the end map question number to letter (A-D). Use them when present.\n"
        "- Each question needs: number, title, four options (A-D), correct_index (0=A..3=D), detected_answer_method, warnings, source_refs.\n"
        "- Include source_refs pointing to paragraph/line indices you relied on.\n"
        "- If multiple conflicting signals exist, choose the best guess and include a warning.\n"
        "- When the body lacks explicit numeric question markers, treat lines starting with '[' that contain 'p' (e.g., [p1-4]) as question starts and number questions sequentially by appearance. Do not try to match body numbers to the answer key when none exist.\n"
        "- Parse the answer key independently; allow multiple entries per line. If no body numbers exist, align answers to questions by order of appearance (1..N) rather than by matching numbers.\n"
    )
    return guidance + "\nCategory: " + category + "\nDocument signal:\n" + safe_json_dumps(document_signal)


def build_repair_prompt(previous_json: Dict[str, Any], errors: List[str]) -> str:
    return (
        "Your previous output did not pass validation. "
        "Fix the JSON to satisfy the schema without inventing new content. "
        "Return only valid JSON.\n\n"
        f"Errors:\n{safe_json_dumps(errors)}\n\nPrevious JSON:\n{safe_json_dumps(previous_json)}"
    )
