#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python}"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

"$PYTHON" -m uvicorn server:app --host 0.0.0.0 --port "${PORT:-8080}"
