# Repository Guidelines

## Project Structure & Module Organization
- `app.py` contains the Streamlit UI and session flow for upload → parse → edit → export.
- `core/` holds the parsing pipeline: `extract.py` (DOCX/TXT signal), `llm_parse.py` (OpenAI structured output + repair), `validate.py`, `export_csv.py`, and helpers in `utils.py`/`prompts.py`.
- `tests/` contains pytest-based unit tests (currently `tests/test_parsing_samples.py`).
- Root files include `requirements.txt` and run helpers (`run.bat`, `run.command`, `shell.bat`). The `.env` file is local-only.

## Build, Test, and Development Commands
- Create venv: `python -m venv .venv`
- Activate: Windows `.\.venv\Scripts\activate` or macOS/Linux `source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run app: `streamlit run app.py` (or double-click `run.bat`/`run.command`)
- Run tests: `pytest`

## Coding Style & Naming Conventions
- Python, 4-space indentation, PEP 8 conventions; prefer clear, typed helper functions where it improves readability.
- Use `snake_case` for functions/variables; keep module names descriptive (`core/extract.py`, `core/llm_parse.py`).
- Test files follow `tests/test_*.py` and test names start with `test_`.
- Avoid committing large/binary exam samples; they are intentionally ignored via `.gitignore`.

## Testing Guidelines
- Framework: pytest.
- Add or update tests when changing extraction heuristics, schema validation, or CSV formatting.
- Keep tests small and deterministic (prefer in-memory DOCX/TXT fixtures as in `tests/test_parsing_samples.py`).

## Commit & Pull Request Guidelines
- Commit message style seen in history: short, imperative or sentence-case (e.g., `fixed page refs...`) with optional conventional prefixes like `feat:` or `chore:`.
- PRs should include a concise description, tests run (or note if not run), and screenshots for Streamlit UI changes.

## Security & Configuration
- Store secrets in `.env` (`OPENAI_API_KEY`, optional `OPENAI_MODEL`); never commit keys.
- If you change LLM schema or prompts, verify parsing with `pytest` and a sample file before merging.
