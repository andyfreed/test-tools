from typing import Any, Dict, List, Tuple


def validate_parsed_questions(data: Dict[str, Any]) -> List[str]:
    """Return a list of validation error messages."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Parsed output is not an object."]

    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("questions must be a non-empty array.")
        return errors

    for idx, q in enumerate(questions):
        prefix = f"Question {idx + 1}"
        if not isinstance(q, dict):
            errors.append(f"{prefix}: entry is not an object.")
            continue
        number = q.get("number")
        if not isinstance(number, int) or number < 1:
            errors.append(f"{prefix}: number must be integer >=1.")
        title = q.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{prefix}: title is missing.")
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            errors.append(f"{prefix}: options must have exactly 4 items.")
        else:
            for oi, opt in enumerate(options):
                if not isinstance(opt, str) or not opt.strip():
                    errors.append(f"{prefix}: option {oi + 1} is empty.")
        correct_index = q.get("correct_index")
        if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
            errors.append(f"{prefix}: correct_index must be between 0 and 3.")
        dam = q.get("detected_answer_method")
        if dam not in {"asterisk", "highlight", "answer_key", "inferred"}:
            errors.append(f"{prefix}: detected_answer_method invalid.")
    return errors


def recompute_menu_order(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure menu order and numbering align sequentially."""
    sorted_questions = sorted(questions, key=lambda q: q.get("number", 0))
    for i, q in enumerate(sorted_questions, start=1):
        q["menu_order"] = i
    return sorted_questions
