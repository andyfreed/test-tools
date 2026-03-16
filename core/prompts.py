from typing import Any, Dict, List, Optional

from .utils import safe_json_dumps


def build_system_prompt() -> str:
    return (
        "You are an expert exam parser that converts exam documents into structured JSON. "
        "Use only the provided document signal. Do not invent or alter content.\n\n"
        "Every question must have exactly four options in A/B/C/D order and a single correct answer.\n\n"
        "Answer Detection (in priority order):\n"
        "1. Answer key at end of document - maps question numbers to A/B/C/D letters.\n"
        "2. Asterisk markers (*) or (**) surrounding or adjacent to an option.\n"
        "3. Highlight flags (has_highlight: true) on option paragraphs (DOCX only).\n"
        "4. Extraction-level asterisk flags (has_asterisk: true) - verify these against context.\n"
        "5. If no explicit signal exists, set detected_answer_method to 'inferred' and pick the best guess.\n\n"
        "Confidence Rating:\n"
        "- 'high': Answer explicitly marked by answer key, clear asterisk, or highlight with no ambiguity.\n"
        "- 'medium': Signal exists but with minor ambiguity (e.g., unclear asterisk placement, partial match, single weak signal).\n"
        "- 'low': No explicit signal found; answer was inferred from context.\n\n"
        "Conflict Resolution:\n"
        "If multiple signals disagree, choose the most reliable (answer_key > highlight > asterisk > inferred), "
        "add a warning explaining the conflict, and set confidence to 'medium' or lower."
    )


def build_user_prompt(document_signal: List[Dict[str, Any]], category: str) -> str:
    guidance = (
        "Document signal is a faithful extraction of the source.\n"
        "Rules:\n"
        "- Asterisks (*) or (**) surrounding or preceding/following an option mean that option is correct; strip asterisks in output.\n"
        "- Items flagged with has_asterisk: true were detected at extraction as having asterisk markers - use this as a strong signal but verify against context.\n"
        "- In DOCX, any option paragraph with has_highlight: true marks the correct answer.\n"
        "- DOCX list numbering can be omitted in extracted text; do not warn about missing A/B/C/D prefixes if options appear as a four-option block.\n"
        "- Lines that start with roman numerals (I., II., III., IV., etc.) are part of the question stem; keep them in the title until A-D options begin.\n"
        "- If a question has a list of statements (often implicitly I/II/III) followed by combined-choice options like 'I only', 'I & II only', 'Both I & II', 'Neither I nor II', treat the statement lines as part of the stem; the combined-choice lines are the options.\n"
        "- Answer keys at the end map question number to letter (A-D). Use them when present.\n"
        "- Each question needs: number, title, four options (A-D), correct_index (0=A..3=D), detected_answer_method, confidence, warnings, source_refs.\n"
        "- Include source_refs pointing to paragraph/line indices you relied on.\n"
        "- If multiple conflicting signals exist, choose the most reliable and include a warning describing the conflict.\n"
        "- If two or more options have identical or near-identical text, add a warning: 'Duplicate or near-duplicate options detected'.\n"
        "- Do not drop a question if its numeric prefix is missing or numbering skips; include it and number by order of appearance.\n"
        "- When the body lacks explicit numeric question markers, treat lines starting with '[' that contain 'p' (e.g., [p1-4]) as question starts and number questions sequentially by appearance. Do not try to match body numbers to the answer key when none exist.\n"
        "- Parse the answer key independently; allow multiple entries per line. If no body numbers exist, align answers to questions by order of appearance (1..N) rather than by matching numbers.\n"
    )
    return guidance + "\nCategory: " + category + "\nDocument signal:\n" + safe_json_dumps(document_signal)


def build_repair_prompt(
    previous_json: Dict[str, Any],
    errors: List[str],
    document_signal: Optional[List[Dict[str, Any]]] = None,
) -> str:
    prompt = (
        "Your previous output did not pass validation. "
        "Fix the JSON to satisfy the schema without inventing new content. "
        "Return only valid JSON.\n\n"
        f"Errors:\n{safe_json_dumps(errors)}\n\n"
    )
    if document_signal:
        prompt += (
            "Original document signal (re-reference as needed):\n"
            + safe_json_dumps(document_signal)
            + "\n\n"
        )
    prompt += f"Previous JSON to fix:\n{safe_json_dumps(previous_json)}"
    return prompt
