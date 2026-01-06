import json
import os
from typing import List

import pandas as pd
import streamlit as st

from core.export_csv import build_csv_bytes
from core.extract import build_document_signals
from core.llm_parse import parse_with_llm
from core.utils import (
    editor_rows_to_questions,
    normalize_question_fields,
    normalize_questions_for_editor,
    safe_json_dumps,
)
from core.validate import validate_parsed_questions


st.set_page_config(page_title="Exam Import Converter", layout="wide")

# Session defaults
for key, default in {
    "parsed": {},
    "validation_errors": [],
    "raw_outputs": [],
    "signals": [],
    "table_rows": [],
    "category": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


st.sidebar.header("Import")
uploaded_files = st.sidebar.file_uploader(
    "Upload DOCX or TXT exam files", type=["docx", "txt"], accept_multiple_files=True
)
category = st.sidebar.text_input("Category", value=st.session_state.get("category", ""))
debug_mode = st.sidebar.toggle("Debug mode", value=False, help="Show document signal and raw model output")
model_default = os.getenv("OPENAI_MODEL", "gpt-5.2")
allowed_models = ["gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4o-mini", "o4-mini"]
model_choice = st.sidebar.selectbox("Model", options=allowed_models + ["Custom"], index=0)
if model_choice == "Custom":
    model = st.sidebar.text_input("Custom model", value=model_default)
else:
    model = model_choice

parse_clicked = st.sidebar.button("Parse & Preview", use_container_width=True)

if parse_clicked:
    if not uploaded_files:
        st.error("Upload at least one .docx or .txt file.")
    else:
        with st.spinner("Parsing with OpenAI..."):
            try:
                signals = build_document_signals(uploaded_files)
                parsed, errors, raw_outputs = parse_with_llm(signals, category or "", model=model)
            except Exception as exc:  # noqa: BLE001 - show user-friendly errors
                st.error(f"Parsing failed: {exc}")
            else:
                st.session_state["signals"] = signals
                if parsed and isinstance(parsed, dict):
                    parsed.setdefault("category", category)
                st.session_state["parsed"] = parsed or {}
                st.session_state["raw_outputs"] = raw_outputs
                st.session_state["validation_errors"] = errors
                st.session_state["category"] = parsed.get("category", category) if isinstance(parsed, dict) else category
                if parsed and isinstance(parsed, dict):
                    rows = normalize_questions_for_editor(parsed.get("questions", []))
                    st.session_state["table_rows"] = rows


st.title("Exam Import Converter")
st.write("Convert DOCX/TXT exam questions into CSV for import. Parse automatically, review, edit, and export.")

# Tracked changes warning
signals = st.session_state.get("signals", [])
if any(sig.get("has_tracked_changes") for sig in signals if isinstance(sig, dict)):
    st.warning("Tracked changes detected. Accept all changes in Word for best results.")

# Summary panel
parsed = st.session_state.get("parsed", {}) if isinstance(st.session_state.get("parsed", {}), dict) else {}
questions = parsed.get("questions", []) if isinstance(parsed, dict) else []
total_questions = len(questions)
validation_errors = st.session_state.get("validation_errors", []) or []
warnings_count = sum(len(q.get("warnings", []) or []) for q in questions if isinstance(q, dict))
tracked_files = [sig.get("source_filename") for sig in signals if isinstance(sig, dict) and sig.get("has_tracked_changes")]

with st.container():
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total questions", total_questions)
    col2.metric("Blocking errors", len(validation_errors))
    col3.metric("Warnings", warnings_count)
    col4.metric("Files with tracked changes", len(tracked_files))

table_rows: List[dict] = st.session_state.get("table_rows", [])
if table_rows:
    st.subheader("Preview & Manual Overrides")
    df = pd.DataFrame(table_rows)
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="questions_editor",
        column_config={
            "number": st.column_config.NumberColumn("Question #", disabled=True),
            "title": st.column_config.TextColumn("Title"),
            "option_A": st.column_config.TextColumn("Option A"),
            "option_B": st.column_config.TextColumn("Option B"),
            "option_C": st.column_config.TextColumn("Option C"),
            "option_D": st.column_config.TextColumn("Option D"),
            "correct_letter": st.column_config.SelectboxColumn("Correct", options=["A", "B", "C", "D"]),
            "detected_answer_method": st.column_config.SelectboxColumn(
                "Detected method",
                options=["asterisk", "highlight", "answer_key", "inferred"],
                disabled=True,
            ),
            "warnings": st.column_config.TextColumn("Warnings", disabled=True),
            "delete": st.column_config.CheckboxColumn("Delete", default=False),
        },
    )

    if st.button("Apply manual edits", type="primary"):
        rows = edited_df.to_dict(orient="records")
        st.session_state["table_rows"] = rows
        updated_questions = editor_rows_to_questions(rows)
        normalized_questions = [normalize_question_fields(q) for q in updated_questions]
        st.session_state["parsed"]["questions"] = normalized_questions
        st.session_state["parsed"]["category"] = category
        st.session_state["validation_errors"] = validate_parsed_questions(st.session_state["parsed"])
        st.success("Manual edits applied and re-validated.")

    parsed = st.session_state.get("parsed", {})
    if isinstance(parsed, dict) and parsed.get("questions"):
        warning_questions = [
            (q.get("number"), q.get("warnings") or [])
            for q in parsed["questions"]
            if q.get("warnings")
        ]
        if warning_questions:
            st.subheader("Warnings")
            for number, warns in warning_questions:
                warns_list = warns if isinstance(warns, list) else [warns]
                with st.expander(f"Question {number} warnings", expanded=False):
                    for w in warns_list:
                        st.write(f"- {w}")

validation_errors = st.session_state.get("validation_errors", [])
if validation_errors:
    st.error("Validation errors:")
    for err in validation_errors:
        st.write(f"- {err}")

can_export = bool(st.session_state.get("parsed")) and not validation_errors
if not table_rows:
    st.info("Upload files and click Parse & Preview to see questions here.")

if can_export:
    csv_bytes = build_csv_bytes(st.session_state["parsed"], st.session_state.get("category", ""))
else:
    csv_bytes = b""

st.download_button(
    label="Export CSV",
    data=csv_bytes,
    file_name="exam-import.csv",
    mime="text/csv",
    disabled=not can_export,
    type="primary",
    use_container_width=True,
)


if debug_mode:
    st.divider()
    st.subheader("Debug")
    if signals:
        st.caption("Extraction metrics")
        for sig in signals:
            counts = sig.get("debug_counts") if isinstance(sig, dict) else None
            if counts:
                st.write(
                    {
                        "file": sig.get("source_filename"),
                        "total_lines": counts.get("total_lines"),
                        "question_starts": counts.get("question_starts"),
                        "option_lines": counts.get("option_lines"),
                        "answer_key_entries": counts.get("answer_key_entries"),
                    }
                )
    st.caption("Document signal")
    st.code(safe_json_dumps(st.session_state.get("signals", [])), language="json")
    st.caption("Raw model outputs")
    for i, raw in enumerate(st.session_state.get("raw_outputs", []), start=1):
        st.code(raw or f"(empty response {i})")
