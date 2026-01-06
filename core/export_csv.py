import csv
import io
import os
from typing import Dict, List, Sequence

from .utils import index_to_letter, normalize_text
from .validate import recompute_menu_order


DEFAULT_HEADERS = [
    "ID",
    "Title",
    "Category",
    "Type",
    "Post Content",
    "Status",
    "Menu Order",
    "Options",
    "Answer",
]


def _headers_from_example(example_path: str = "example-output.csv") -> List[str]:
    if not os.path.exists(example_path):
        return DEFAULT_HEADERS
    with open(example_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            return row
    return DEFAULT_HEADERS


def _options_to_string(options: Sequence[str]) -> str:
    return "|".join(options)


def build_csv_bytes(parsed: Dict[str, List[Dict]], category: str) -> bytes:
    headers = _headers_from_example()
    questions = recompute_menu_order(parsed.get("questions", []))

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for q in questions:
        options = [normalize_text(opt) for opt in q.get("options", ["", "", "", ""])]
        correct_index = q.get("correct_index", 0)
        answer = options[correct_index] if 0 <= correct_index < len(options) else ""
        row = {
            "ID": "",
            "Title": normalize_text(q.get("title", "")),
            "Category": normalize_text(category),
            "Type": "single-choice",
            "Post Content": normalize_text(q.get("title", "")),
            "Status": "publish",
            "Menu Order": q.get("menu_order", 0),
            "Options": _options_to_string(options),
            "Answer": answer,
        }
        # Ensure additional headers remain in place with blank defaults
        for h in headers:
            if h not in row:
                row[h] = ""
        writer.writerow(row)

    return output.getvalue().encode("utf-8")
