@echo off
cd /d %~dp0

REM Always use the venv python directly (no relying on PATH)
set "VENV_PY=%CD%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo ERROR: venv python not found at "%VENV_PY%"
  echo Create it with: py -m venv .venv
  pause
  exit /b 1
)

echo Using: %VENV_PY%
"%VENV_PY%" -m pip install -r requirements.txt

echo.
echo VENV READY. Opening a shell with venv python available.
echo Type commands like:
echo   %VENV_PY% -m streamlit run app.py
echo.

cmd /k
