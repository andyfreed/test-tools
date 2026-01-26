import io
import os
import tempfile

from docx import Document
from docx.enum.text import WD_COLOR_INDEX

from core.extract import extract_docx, extract_txt
from core.utils import normalize_text
from core.validate import validate_parsed_questions


def _build_sample_docx() -> bytes:
    doc = Document()
    doc.add_paragraph("Sample Question 1")
    doc.add_paragraph("*Option A")
    p = doc.add_paragraph("Option B")
    run = p.add_run(" (highlighted)")
    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    doc.add_paragraph("Option C")
    doc.add_paragraph("Option D")
    file_obj = io.BytesIO()
    doc.save(file_obj)
    return file_obj.getvalue()


def test_extract_docx_highlight_detection():
    content = _build_sample_docx()
    signal = extract_docx(content, "sample.docx")
    assert signal["content_type"] == "docx"
    has_highlight = any(p["has_highlight"] for p in signal["paragraphs"])
    assert has_highlight, "Expected at least one highlighted paragraph"


def test_extract_txt_lines():
    content = b"Q1: Sample?\nA) One\n\nB) Two\n"
    signal = extract_txt(content, "sample.txt")
    texts = [l["text"] for l in signal["lines"]]
    assert "Q1: Sample?" in texts
    assert len(texts) == 3  # skips empty line


def test_validation():
    good = {
        "category": "Demo",
        "questions": [
            {
                "number": 1,
                "title": "What is 2+2?",
                "options": ["1", "2", "3", "4"],
                "correct_index": 3,
                "detected_answer_method": "asterisk",
                "warnings": [],
                "source_refs": [{"kind": "paragraph", "index": 0}],
            }
        ],
    }
    assert validate_parsed_questions(good) == []

    bad = {"category": "Demo", "questions": [{"number": 0, "title": "", "options": [], "correct_index": 5}]}
    errors = validate_parsed_questions(bad)
    assert errors, "Validation should find errors for bad payload"


def test_normalize_text_mojibake_cleanup():
    assert normalize_text("Reduce the modelâ€™s complexity") == "Reduce the model's complexity"
    assert normalize_text("Reduce the modelâs complexity") == "Reduce the model's complexity"
    assert normalize_text("Precision Ã— Recall") == "Precision × Recall"
