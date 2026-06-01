#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-python}"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

"$PYTHON" aliyun_ops_mcp.py
