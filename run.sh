#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.9+ 가 필요합니다: https://www.python.org/downloads/"; exit 1; }

[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -q --upgrade pip
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt

echo "대시보드 실행: http://127.0.0.1:8000  (종료: Ctrl+C)"
exec .venv/bin/python -m app
