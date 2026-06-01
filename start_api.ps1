$ErrorActionPreference = "Stop"

$Python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python -m uvicorn server:app --host 0.0.0.0 --port 8080
