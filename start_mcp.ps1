$ErrorActionPreference = "Stop"

$Python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python .\aliyun_ops_mcp.py
