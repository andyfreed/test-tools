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
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


st.sidebar.markdown(
    """
<div class="section-card info-card sidebar-card">
  <div class="sidebar-title">Before you upload</div>
  <ol class="sidebar-list">
    <li>Open the exam Word file from the author.</li>
    <li>Accept all changes and stop tracking.</li>
    <li>Remove chapter headings and anything other than the test questions and answer key (if applicable).</li>
    <li>Save the file, then upload it here.</li>
  </ol>
</div>
    """,
    unsafe_allow_html=True,
)
uploaded_files = st.sidebar.file_uploader(
    "", type=["docx", "txt"], accept_multiple_files=True
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
            finally:
                modal_placeholder.empty()


st.markdown(
    """
 <style>
 @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap');
 :root {
   --bg0: #000000;
   --bg1: #141414;

   --surface: rgba(0, 0, 0, 0.92);
   --surface-border: rgba(255, 255, 255, 0.14);
   --card: #050505;
   --card-border: rgba(255, 255, 255, 0.16);

   --text: #f8fafc;
   --muted: #b3b3b3;
   --accent: #111111;
   --accent-2: #111111;

   --sidebar-bg: rgba(0, 0, 0, 0.96);
   --sidebar-text: rgba(255, 255, 255, 0.92);
   --sidebar-muted: rgba(255, 255, 255, 0.72);

   --shadow: rgba(0, 0, 0, 0.28);
 }

 html, body {
   font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
 }
 h1, h2, h3, h4 {
   font-family: 'Space Grotesk', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
   letter-spacing: -0.015em;
 }

 /* Background */
 .stApp {
   background:
     radial-gradient(1000px circle at 12% 0%, rgba(255, 255, 255, 0.12), transparent 45%),
     radial-gradient(900px circle at 92% 10%, rgba(255, 255, 255, 0.08), transparent 46%),
     linear-gradient(135deg, var(--bg0), var(--bg1));
 }
 [data-testid="stAppViewContainer"] > .main {
   background: transparent;
 }

 /* Main panel */
 section.main .block-container {
   background: radial-gradient(circle at 10% -20%, rgba(255, 255, 255, 0.12), transparent 45%),
     radial-gradient(circle at 85% 0%, rgba(255, 255, 255, 0.08), transparent 40%),
     var(--surface);
   border: 1px solid var(--surface-border);
   border-radius: 18px;
   padding: 1.5rem 1.75rem;
   box-shadow: 0 18px 45px rgba(0, 0, 0, 0.6);
   margin-top: 0.75rem;
   margin-bottom: 1.5rem;
 }
 section.main .block-container,
 section.main .block-container p,
 section.main .block-container li,
 section.main .block-container label {
   color: var(--text) !important;
 }
 section.main h1, section.main h2, section.main h3, section.main h4, section.main h5, section.main h6 {
   color: var(--text) !important;
 }
 section.main .stCaption {
   color: var(--muted) !important;
 }
 section.main .block-container .stMarkdown p,
 section.main .block-container .stMarkdown li {
   color: var(--text) !important;
   line-height: 1.55;
 }
 section.main .block-container .stMarkdown a {
   color: #ffffff !important;
 }

 /* Hero */
 .hero {
   background: linear-gradient(135deg, #000000, #202020);
   color: rgba(248, 250, 252, 0.95);
   border: 1px solid rgba(255, 255, 255, 0.22);
   padding: 1.25rem 1.5rem;
   border-radius: 16px;
   box-shadow: 0 16px 50px rgba(0, 0, 0, 0.55);
   margin-bottom: 1rem;
 }
 .hero * {
   color: inherit;
 }
 .hero .kicker {
   text-transform: uppercase;
   font-size: 0.75rem;
   letter-spacing: 0.2em;
   color: #ffffff;
   margin-bottom: 0.35rem;
 }
 .hero .title {
   font-size: 2.1rem;
   margin: 0;
 }
 .hero .subtitle {
   color: rgba(248, 250, 252, 0.82);
   margin-top: 0.5rem;
 }

 /* Cards */
 .section-card {
   background: linear-gradient(135deg, #050505, #0f0f0f);
   border: 1px solid var(--card-border);
   padding: 1rem 1.25rem;
   border-radius: 14px;
   box-shadow: 0 12px 30px rgba(0, 0, 0, 0.55);
   color: #ffffff;
 }
 .section-card * {
   color: inherit !important;
 }
 .info-card {
   border: none !important;
   box-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
 }
 .sidebar-card {
   padding: 0.9rem 1rem;
   background: #060606;
   border-radius: 16px;
 }
 .sidebar-title {
   font-size: 0.85rem;
   text-transform: uppercase;
   letter-spacing: 0.12em;
   color: rgba(255, 255, 255, 0.78);
   margin-bottom: 0.6rem;
 }
 .sidebar-list {
   margin: 0;
   padding-left: 1.05rem;
   color: #ffffff;
   line-height: 1.45;
   font-size: 0.9rem;
 }
 .sidebar-list li {
   margin-bottom: 0.45rem;
 }
 .sidebar-list li:last-child {
   margin-bottom: 0;
 }
 .badge {
   display: inline-block;
   padding: 0.25rem 0.6rem;
   border-radius: 999px;
   background: #000000;
   color: #ffffff;
   border: 1px solid #ffffff;
   font-weight: 700;
   font-size: 0.75rem;
 }

 /* Sidebar */
 [data-testid="stSidebar"] {
   background: var(--sidebar-bg);
   border-right: 1px solid rgba(255, 255, 255, 0.08);
 }
 [data-testid="stSidebar"] * {
   color: var(--sidebar-text) !important;
 }
 [data-testid="stSidebar"] label,
 [data-testid="stSidebar"] small,
 [data-testid="stSidebar"] p {
   color: var(--sidebar-muted) !important;
 }
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: rgba(255, 255, 255, 0.08) !important;
  border: 1px solid rgba(255, 255, 255, 0.16) !important;
  border-radius: 10px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
  margin: 0 auto !important;
}
 [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
   background: rgba(255, 255, 255, 0.06) !important;
   border: 1px dashed rgba(255, 255, 255, 0.22) !important;
   border-radius: 14px !important;
   position: relative !important;
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
 }

 /* Tables */
 [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
   background: #0b0b0b;
   border-radius: 12px;
   border: 1px solid rgba(255, 255, 255, 0.16);
 }
 [data-testid="stDataFrame"] *, [data-testid="stDataEditor"] * {
   color: var(--text) !important;
 }

 /* Buttons */
 .stButton > button, .stDownloadButton > button {
   background: #000000 !important;
   color: #ffffff !important;
   border: 1px solid #ffffff !important;
   border-radius: 12px !important;
   font-weight: 800 !important;
   box-shadow: 0 10px 22px rgba(0, 0, 0, 0.2) !important;
 }
 .stButton > button:hover, .stDownloadButton > button:hover {
   background: #111111 !important;
   color: #ffffff !important;
 }
 .stButton > button:disabled, .stDownloadButton > button:disabled {
   background: #000000 !important;
   color: rgba(255, 255, 255, 0.35) !important;
   border: none !important;
   box-shadow: none !important;
   cursor: not-allowed;
 }

 /* Tabs + metrics */
 [data-testid="stMetricLabel"] {
   color: var(--muted) !important;
 }
 [data-testid="stMetricValue"] {
   color: var(--text) !important;
 }
 .stTabs [role="tab"] {
   color: #ffffff !important;
   font-weight: 700;
 }
 .stTabs [role="tab"][aria-selected="true"] {
   color: #ffffff !important;
 }
 .stTabs [role="tablist"] {
   background: #000000;
   border-radius: 999px;
   padding: 0.25rem;
 }
 .stTabs [role="tab"][aria-selected="true"]::after {
   background: #ffffff !important;
 }

 /* Alerts */
 [data-testid="stAlert"],
 [data-baseweb="notification"],
 [role="alert"] {
   background: #0b0b0b !important;
   color: #ffffff !important;
   border: 1px solid #ffffff !important;
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

 /* Video modal */
 .video-modal-backdrop {
   position: fixed;
   inset: 0;
   background: rgba(0, 0, 0, 0.72);
   display: flex;
   align-items: center;
   justify-content: center;
   z-index: 9999;
 }
 .video-modal {
   width: min(720px, 90vw);
   aspect-ratio: 16 / 9;
   border-radius: 16px;
   overflow: hidden;
   border: 1px solid rgba(255, 255, 255, 0.18);
   box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
 }
 .video-modal iframe {
   width: 100%;
   height: 100%;
 }
 </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <div class="title">Exam Converter</div>
</div>
    """,
    unsafe_allow_html=True,
)

tab_exam, tab_future = st.tabs(["Exam Converter", "Another Converter (Coming Soon)"])

with tab_exam:
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
        pass

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

with tab_future:
    st.subheader("New Converter Slot")
    st.markdown(
        """
<div class="section-card">
  <span class="badge">Ready for next format</span>
  <p><strong>Purpose:</strong> This space is reserved for a future converter targeting a different document type.</p>
  <p><strong>Planned flow:</strong> upload → signal extraction → LLM parse → validation → export.</p>
  <p>When you are ready, we can add a dedicated uploader, schema, and output mapping here without disturbing the exam pipeline.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
