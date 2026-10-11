@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.9+ is required. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv || (echo [ERROR] Failed to create venv & pause & exit /b 1)
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo [ERROR] pip install failed & pause & exit /b 1)

echo Starting dashboard at http://127.0.0.1:8000  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m app
pause
