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


st.set_page_config(page_title="Exam Converter", layout="wide")

# Session defaults
for key, default in {
    "parsed": {},
    "validation_errors": [],
    "raw_outputs": [],
    "signals": [],
    "table_rows": [],
    "category": "",
    "require_reload": False,
    "last_upload_fingerprint": None,
    "uploader_key": "uploaded_files_v1",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


reset_clicked = st.sidebar.button("Reset", use_container_width=True)
if reset_clicked:
    st.session_state.clear()
    st.session_state["category"] = ""
    st.session_state["uploaded_files"] = None
    st.rerun()

st.sidebar.markdown(
    """
<div class="instructions-card">
  <h4 class="instructions-title">Instructions</h4>
  <ol class="instructions-list">
    <li>Open the exam Word file from the author</li>
    <li>Accept all changes and stop tracking</li>
    <li>Remove chapter headings and anything other than the test questions and answer key</li>
    <li>Save the file, then upload it here</li>
  </ol>
</div>
    """,
    unsafe_allow_html=True,
)
uploaded_files = st.sidebar.file_uploader(
    "Upload exam files",
    type=["docx", "txt"],
    accept_multiple_files=True,
    key=st.session_state.get("uploader_key", "uploaded_files_v1"),
    label_visibility="collapsed",
)
category = st.sidebar.text_input("Category", value=st.session_state.get("category", ""), placeholder="e.g. Chapter 1")

model_default = os.getenv("OPENAI_MODEL", "gpt-5.5")
allowed_models = ["gpt-5.5", "gpt-5.5-pro", "gpt-5.4", "gpt-5.4-pro", "gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4o-mini", "o4-mini", "claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"]
model_options = allowed_models + ["Custom"]
default_model_choice = model_default if model_default in allowed_models else "Custom"
model_choice = st.sidebar.selectbox(
    "Model",
    options=model_options,
    index=model_options.index(default_model_choice),
)
if model_choice == "Custom":
    model = st.sidebar.text_input("Custom model", value=model_default, placeholder="Custom model ID")
else:
    model = model_choice

docx_as_txt = st.sidebar.toggle("Convert DOCX to TXT first", value=False, help="Extract plain text from DOCX before parsing (can improve results for some files)")
debug_mode = st.sidebar.toggle("Debug mode", value=False, help="Show document signal and raw model output")

if uploaded_files:
    current_fingerprint = tuple((f.name, f.size) for f in uploaded_files)
    if current_fingerprint != st.session_state.get("last_upload_fingerprint"):
        st.session_state["last_upload_fingerprint"] = current_fingerprint
        st.session_state["require_reload"] = False

parse_clicked = st.sidebar.button("Parse & Preview", use_container_width=True)

if parse_clicked:
    if not uploaded_files:
        st.error("Upload at least one .docx or .txt file.")
    elif st.session_state.get("require_reload"):
        st.error("Please re-upload files before parsing again.")
    else:
        with st.spinner("Parsing..."):
            progress_bar = st.progress(0, text="Extracting document signal...")
            modal_placeholder = st.empty()
            modal_placeholder.markdown(
                """
<div class="video-modal-backdrop">
  <div class="video-modal">
    <iframe
      src="https://www.youtube.com/embed/31RZ5wU-Fg0?start=360&autoplay=1&mute=1&rel=0"
      title="Parsing in progress"
      frameborder="0"
      allow="autoplay; encrypted-media"
      allowfullscreen
    ></iframe>
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )
            try:
                signals = build_document_signals(uploaded_files, docx_as_txt=docx_as_txt)
                progress_bar.progress(5, text="Sending to LLM...")

                def _on_chunk(completed: int, total: int) -> None:
                    pct = int(5 + 90 * completed / total)
                    progress_bar.progress(pct, text=f"Chunk {completed}/{total} complete")

                parsed, errors, raw_outputs = parse_with_llm(
                    signals, category or "", model=model, on_chunk_complete=_on_chunk,
                )
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
                st.session_state["require_reload"] = True
                st.session_state["last_upload_fingerprint"] = None
                st.session_state["uploader_key"] = f"uploaded_files_v{int(st.session_state.get('uploader_key', 'uploaded_files_v1').split('_v')[-1]) + 1}"
            finally:
                modal_placeholder.empty()
                progress_bar.empty()


# ---------------------------------------------------------------------------
# Styles — adapted from Figma design
# ---------------------------------------------------------------------------
st.markdown(
    """
 <style>
 @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap');

 html, body {
   font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
 }
 h1, h2, h3, h4 {
   font-family: 'Space Grotesk', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
   letter-spacing: -0.015em;
 }

 /* ── App background ── */
 .stApp {
   background: #0e0e0e;
 }
 [data-testid="stAppViewContainer"] > .main {
   background: transparent;
 }

 /* ── Main panel ── */
 section.main .block-container {
   background: transparent;
   padding: 1.5rem 1.75rem;
   margin-top: 0.75rem;
   margin-bottom: 1.5rem;
 }
 section.main .block-container,
 section.main .block-container p,
 section.main .block-container li,
 section.main .block-container label {
   color: #f8fafc !important;
 }
 section.main h1, section.main h2, section.main h3,
 section.main h4, section.main h5, section.main h6 {
   color: #f8fafc !important;
 }
 section.main .stCaption {
   color: rgba(255,255,255,0.5) !important;
 }
 section.main .block-container .stMarkdown p,
 section.main .block-container .stMarkdown li {
   color: #f8fafc !important;
   line-height: 1.55;
 }
 section.main .block-container .stMarkdown a {
   color: #ffffff !important;
 }

 /* ── Hero banner ── */
 .hero {
   background: linear-gradient(to right, #050505, #0f0f0f);
   color: #ffffff;
   border: 1px solid rgba(255,255,255,0.10);
   padding: 1.5rem;
   border-radius: 16px;
   margin-bottom: 1.5rem;
 }
 .hero .title {
   font-family: 'Space Grotesk', sans-serif;
   font-size: 1.75rem;
   font-weight: 600;
   margin: 0;
   color: #ffffff;
 }

 /* ── Instructions card (sidebar) ── */
 .instructions-card {
   background: linear-gradient(to bottom, #050505, #0f0f0f);
   border: 1px solid rgba(255,255,255,0.10);
   border-radius: 14px;
   padding: 1rem;
 }
 .instructions-title {
   font-family: 'Space Grotesk', sans-serif;
   color: rgba(255,255,255,0.9) !important;
   font-size: 0.85rem;
   margin-bottom: 0.5rem;
 }
 .instructions-list {
   margin: 0;
   padding-left: 1.1rem;
   color: rgba(255,255,255,0.6) !important;
   font-size: 0.85rem;
   line-height: 1.5;
 }
 .instructions-list li {
   margin-bottom: 0.35rem;
   color: rgba(255,255,255,0.6) !important;
 }
 .instructions-list li:last-child { margin-bottom: 0; }

 /* ── Generic card ── */
 .section-card {
   background: linear-gradient(to bottom, #050505, #0f0f0f);
   border: 1px solid rgba(255,255,255,0.10);
   padding: 1rem 1.25rem;
   border-radius: 14px;
   color: #ffffff;
 }
 .section-card * { color: inherit !important; }
 .badge {
   display: inline-block;
   padding: 0.25rem 0.75rem;
   border-radius: 999px;
   background: rgba(255,255,255,0.10);
   color: rgba(255,255,255,0.6);
   font-size: 0.75rem;
   border: none;
 }

 /* ── Sidebar ── */
 [data-testid="stSidebar"] {
   background: #0a0a0a;
   border-right: 1px solid rgba(255,255,255,0.10);
 }
 [data-testid="stSidebar"] * {
   color: rgba(255,255,255,0.92) !important;
 }
 [data-testid="stSidebar"] label,
 [data-testid="stSidebar"] small,
 [data-testid="stSidebar"] p {
   color: rgba(255,255,255,0.70) !important;
 }
 [data-testid="stSidebar"] input,
 [data-testid="stSidebar"] textarea,
 [data-testid="stSidebar"] [data-baseweb="select"] > div {
   background: rgba(255,255,255,0.05) !important;
   border: 1px solid rgba(255,255,255,0.10) !important;
   border-radius: 10px !important;
 }
 [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
   margin: 0 auto !important;
 }
 [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
   background: transparent !important;
   border: 2px dashed rgba(255,255,255,0.15) !important;
   border-radius: 14px !important;
   padding-top: 1.5rem !important;
   padding-bottom: 1.5rem !important;
   display: flex !important;
   flex-direction: column !important;
   align-items: center !important;
   justify-content: center !important;
   gap: 0.5rem !important;
 }
 [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"] {
   display: none !important;
 }

 /* ── Metrics ── */
 [data-testid="stMetricLabel"] {
   color: rgba(255,255,255,0.5) !important;
   font-size: 0.75rem !important;
 }
 [data-testid="stMetricValue"] {
   color: #ffffff !important;
   font-family: 'Space Grotesk', sans-serif !important;
 }
 [data-testid="stMetric"] {
   background: linear-gradient(to bottom, #050505, #0f0f0f);
   border: 1px solid rgba(255,255,255,0.10);
   border-radius: 14px;
   padding: 1rem;
 }

 /* ── Tables ── */
 [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
   background: linear-gradient(to bottom, #050505, #0f0f0f);
   border-radius: 14px;
   border: 1px solid rgba(255,255,255,0.10);
   overflow: hidden;
 }
 [data-testid="stDataFrame"] *, [data-testid="stDataEditor"] * {
   color: #f8fafc !important;
 }

 /* ── Buttons ── */
 .stButton > button, .stDownloadButton > button {
   background: #000000 !important;
   color: #ffffff !important;
   border: 1px solid rgba(255,255,255,0.20) !important;
   border-radius: 12px !important;
   font-weight: 500 !important;
   transition: background 0.15s ease !important;
 }
 .stButton > button:hover, .stDownloadButton > button:hover {
   background: rgba(255,255,255,0.05) !important;
   color: #ffffff !important;
 }
 .stButton > button:disabled, .stDownloadButton > button:disabled {
   background: #000000 !important;
   color: rgba(255,255,255,0.30) !important;
   border: 1px solid transparent !important;
   cursor: not-allowed;
 }

 /* ── Tabs ── */
 .stTabs [role="tablist"] {
   background: transparent;
   border-bottom: 1px solid rgba(255,255,255,0.10);
   gap: 0.25rem;
 }
 .stTabs [role="tab"] {
   color: rgba(255,255,255,0.50) !important;
   font-weight: 500;
   border-radius: 8px 8px 0 0;
   padding: 0.625rem 1rem;
 }
 .stTabs [role="tab"]:hover {
   color: rgba(255,255,255,0.70) !important;
 }
 .stTabs [role="tab"][aria-selected="true"] {
   color: #ffffff !important;
   background: rgba(255,255,255,0.10);
 }
 .stTabs [role="tab"][aria-selected="true"]::after {
   background: #ffffff !important;
   height: 2px !important;
 }

 /* ── Alerts ── */
 [data-testid="stAlert"][data-baseweb-type="warning"],
 .warning-alert {
   background: rgba(234,179,8,0.10) !important;
   border: 1px solid rgba(234,179,8,0.30) !important;
   border-radius: 14px !important;
 }
 [data-testid="stAlert"][data-baseweb-type="error"],
 .error-alert {
   background: rgba(239,68,68,0.10) !important;
   border: 1px solid rgba(239,68,68,0.30) !important;
   border-radius: 14px !important;
 }
 [data-testid="stAlert"],
 [data-baseweb="notification"],
 [role="alert"] {
   background: rgba(255,255,255,0.05) !important;
   color: #ffffff !important;
   border: 1px solid rgba(255,255,255,0.10) !important;
   border-radius: 14px !important;
   box-shadow: none !important;
 }
 [data-testid="stAlert"] *,
 [data-baseweb="notification"] *,
 [role="alert"] * {
   color: #ffffff !important;
 }
 [data-testid="stAlert"] svg,
 [data-baseweb="notification"] svg,
 [role="alert"] svg {
   color: #ffffff !important;
   fill: #ffffff !important;
 }

 /* ── Expander (warnings) ── */
 .streamlit-expanderHeader {
   background: transparent !important;
   border: 1px solid rgba(255,255,255,0.10) !important;
   border-radius: 10px !important;
   color: rgba(255,255,255,0.70) !important;
 }
 .streamlit-expanderContent {
   border: 1px solid rgba(255,255,255,0.10) !important;
   border-top: none !important;
   border-radius: 0 0 10px 10px !important;
 }

 /* ── Progress bar ── */
 [data-testid="stProgress"] > div > div {
   background: rgba(255,255,255,0.10) !important;
   border-radius: 999px !important;
 }
 [data-testid="stProgress"] > div > div > div {
   background: rgba(255,255,255,0.60) !important;
   border-radius: 999px !important;
 }

 /* ── Confidence badges via data-editor ── */
 /* These are handled by Streamlit's built-in rendering */

 /* ── Video modal ── */
 .video-modal-backdrop {
   position: fixed;
   inset: 0;
   background: rgba(0,0,0,0.72);
   display: flex;
   align-items: center;
   justify-content: center;
   z-index: 9999;
 }
 .video-modal {
   width: min(1920px, 96vw);
   aspect-ratio: 16 / 9;
   border-radius: 16px;
   overflow: hidden;
   border: 1px solid rgba(255,255,255,0.18);
   box-shadow: 0 24px 80px rgba(0,0,0,0.6);
 }
 .video-modal iframe {
   width: 100%;
   height: 100%;
 }

 /* ── Empty state ── */
 .empty-state {
   display: flex;
   flex-direction: column;
   align-items: center;
   justify-content: center;
   padding: 5rem 1rem;
   color: rgba(255,255,255,0.30);
 }
 .empty-state svg {
   width: 48px;
   height: 48px;
   margin-bottom: 1rem;
   stroke: currentColor;
   fill: none;
 }
 .empty-state p {
   color: rgba(255,255,255,0.30) !important;
   font-size: 0.95rem;
 }
 </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="hero">
  <div class="title">Exam Converter V1.3</div>
</div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_exam, tab_future = st.tabs(["Exam Converter", "Another Converter (Coming Soon)"])

with tab_exam:
    # Tracked changes warning
    signals = st.session_state.get("signals", [])
    if any(sig.get("has_tracked_changes") for sig in signals if isinstance(sig, dict)):
        st.warning("Tracked changes detected. Accept all changes in Word for best results.")

    # Summary metrics
    parsed = st.session_state.get("parsed", {}) if isinstance(st.session_state.get("parsed", {}), dict) else {}
    questions = parsed.get("questions", []) if isinstance(parsed, dict) else []
    total_questions = len(questions)
    validation_errors = st.session_state.get("validation_errors", []) or []
    warnings_count = sum(len(q.get("warnings", []) or []) for q in questions if isinstance(q, dict))
    tracked_files = [
        sig.get("source_filename")
        for sig in signals
        if isinstance(sig, dict) and sig.get("has_tracked_changes")
    ]

    with st.container():
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total questions", total_questions)
        col2.metric("Blocking errors", len(validation_errors))
        col3.metric("Warnings", warnings_count)
        col4.metric("Files w/ tracked changes", len(tracked_files))

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
                "number": st.column_config.NumberColumn("#", disabled=True, width="small"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "option_A": st.column_config.TextColumn("A"),
                "option_B": st.column_config.TextColumn("B"),
                "option_C": st.column_config.TextColumn("C"),
                "option_D": st.column_config.TextColumn("D"),
                "correct_letter": st.column_config.SelectboxColumn("Correct", options=["A", "B", "C", "D"]),
                "detected_answer_method": st.column_config.SelectboxColumn(
                    "Method",
                    options=["asterisk", "highlight", "answer_key", "inferred"],
                    disabled=True,
                ),
                "confidence": st.column_config.SelectboxColumn(
                    "Conf.",
                    options=["high", "medium", "low"],
                    disabled=True,
                ),
                "warnings": st.column_config.TextColumn("Warnings", disabled=True),
                "delete": st.column_config.CheckboxColumn("Del", default=False),
            },
        )

        if st.button("Apply manual edits", type="primary", use_container_width=True):
            rows = edited_df.to_dict(orient="records")
            st.session_state["table_rows"] = rows
            updated_questions = editor_rows_to_questions(rows)
            normalized_questions = [normalize_question_fields(q) for q in updated_questions]
            st.session_state["parsed"]["questions"] = normalized_questions
            st.session_state["parsed"]["category"] = category
            st.session_state["validation_errors"] = validate_parsed_questions(st.session_state["parsed"])
            st.success("Manual edits applied and re-validated.")

        # Warnings section
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

    # Validation errors
    validation_errors = st.session_state.get("validation_errors", [])
    if validation_errors:
        st.error("Validation errors:")
        for err in validation_errors:
            st.write(f"- {err}")

    # Export
    can_export = bool(st.session_state.get("parsed")) and not validation_errors

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

    # Empty state
    if not table_rows and not validation_errors:
        st.markdown(
            """
<div class="empty-state">
  <svg viewBox="0 0 24 24" stroke-width="1.5">
    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
  <p>Upload exam files and click "Parse & Preview" to begin</p>
</div>
            """,
            unsafe_allow_html=True,
        )

    # Debug section
    if debug_mode:
        st.divider()
        st.subheader("Debug")
        if signals:
            st.caption("Extraction metrics")
            for sig in signals:
                counts = sig.get("debug_counts") if isinstance(sig, dict) else None
                if counts:
                    st.code(json.dumps({
                        "file": sig.get("source_filename"),
                        "total_lines": counts.get("total_lines"),
                        "question_starts": counts.get("question_starts"),
                        "option_lines": counts.get("option_lines"),
                        "answer_key_entries": counts.get("answer_key_entries"),
                    }, indent=2), language="json")
        st.caption("Document signal")
        st.code(safe_json_dumps(st.session_state.get("signals", [])), language="json")
        st.caption("Raw model outputs")
        for i, raw in enumerate(st.session_state.get("raw_outputs", []), start=1):
            st.code(raw or f"(empty response {i})")

with tab_future:
    st.markdown(
        """
<div class="section-card" style="text-align: center; padding: 2rem;">
  <span class="badge">Ready for next format</span>
  <h3 style="font-family: 'Space Grotesk', sans-serif; margin-top: 1rem;">Another Converter</h3>
  <p style="color: rgba(255,255,255,0.5) !important; max-width: 28rem; margin: 0.5rem auto 0;">
    Planned flow: upload &rarr; signal extraction &rarr; LLM parse &rarr; validation &rarr; export
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )
