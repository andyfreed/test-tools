# Exam Import Converter

Streamlit app that turns DOCX/TXT exams into a validated CSV import. Supports mixed authoring styles (asterisks, DOCX highlight, end-of-file answer keys) and uses OpenAI structured output with an auto-repair loop plus schema validation.

## What the app does
- Reads uploaded `.docx` and `.txt` files, builds a document signal, sends it to the LLM with a strict JSON schema, and validates/repairs the result.
- Lets users review and edit questions inline, then exports CSV in the expected column order.
- Shows warnings for tracked changes and encoding/mojibake cleanup.

## Extraction rules (core/extract.py)
- **DOCX paragraphs**: All body paragraphs plus all table cell paragraphs are included. Each entry has a contiguous `line_index` and `has_highlight` flag (true when any run in the paragraph is highlighted).
- **TXT decoding**: Reads bytes, tries `utf-8-sig` → `utf-8` → `cp1252` → `latin-1`, preferring the first decode with minimal `�` replacements. Common UTF-8-as-cp1252 mojibake sequences are fixed (e.g., “â€™” → `'`). Adds warning `Normalized text encoding artifacts` when cleanup occurs.
- **Answer key cleanup**: Strips trailing bracket annotations from lines (regex `\s*\[[^\]]+\]\s*$`) before matching answer keys. Answer key pattern accepts optional “Q”, separators, and A–D letters.
- **Question start patterns**: `^\s*(\d{1,4})[.)]\s+\S` and `^\s*Q(\d{1,4})[:.)]\s+\S` (case-insensitive).
- **Option patterns**: `^\s*[A-D][.)]\s+\S` and `^\s*\(?[A-D]\)\s+\S` (case-insensitive).
- **Line indexing**: Both DOCX and TXT extractions maintain contiguous `line_index` values; empty/irrelevant lines are skipped but numbering stays gapless.
- **Debug counts**: Each signal carries `debug_counts` with totals for `total_lines`, `question_starts`, `option_lines`, and `answer_key_entries` to diagnose under-detection.

## LLM pipeline (core/llm_parse.py, core/prompts.py)
- System/user prompts instruct the model to use only the document signal and to detect answers via asterisks, highlight, or answer keys.
- Uses OpenAI structured outputs (JSON schema `exam_questions_v1`), validates locally, and will attempt up to two auto-repairs if validation fails.
- Normalization (core/utils.py) flattens whitespace, cleans mojibake, and maintains warnings; schema requires: number, title, four options (A–D), correct_index, detected_answer_method (`asterisk|highlight|answer_key|inferred`), warnings, and source_refs.

## UI flow (app.py)
- Sidebar: upload files, set category, toggle Debug mode, click **Parse & Preview**.
- Main pane: preview editable questions; **Apply manual edits** re-validates; **Export CSV** enabled only when validation passes.
- Debug mode shows extraction metrics per file, full document signal, and raw model outputs.
- Tracks files with Word tracked changes and shows a warning.

## Running locally
1) Create a virtual environment  
```
python -m venv .venv
```
2) Activate it  
Windows: `.venv\Scripts\activate`  
macOS/Linux: `source .venv/bin/activate`
3) Install dependencies  
```
pip install -r requirements.txt
```
4) Configure OpenAI  
Create `.env` (or copy `.env.example`) with:  
```
OPENAI_API_KEY=sk-...
```
5) Start the app  
Windows: double-click `run.bat` or run `streamlit run app.py`  
macOS: double-click `run.command` or run `streamlit run app.py`

## Tests
```
pytest
```
