from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ops_core import (
    DEFAULT_TARGET,
    get_disk_io,
    get_host_cpu,
    get_host_disk,
    get_host_inode,
    get_host_system_env,
    get_host_workload,
    get_space,
    get_top_processes,
    run_full_analysis,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web"

app = FastAPI(
    title="AIOps MCP Analyzer",
    description="MCP evidence collector and incident analysis dashboard.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


class AnalyzeRequest(BaseModel):
    target: str | None = Field(default=None, description="Host IP or name. Defaults to the server itself.")
    space_code: str = Field(default="bkcc__131")
    source: str = Field(default="space_list")
    use_llm: bool = Field(default=False)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "default_target": DEFAULT_TARGET}


@app.post("/api/analyze/full")
def analyze_full(payload: AnalyzeRequest) -> dict[str, Any]:
    return run_full_analysis(
        target=payload.target,
        space_code=payload.space_code,
        source=payload.source,
        use_llm=payload.use_llm,
    )


@app.get("/api/analyze/full")
def analyze_full_get(
    target: str | None = None,
    space_code: str = "bkcc__131",
    source: str = "space_list",
    use_llm: bool = False,
) -> dict[str, Any]:
    return run_full_analysis(target=target, space_code=space_code, source=source, use_llm=use_llm)


@app.get("/api/tools/{tool_name}")
def run_tool(tool_name: str, target: str | None = None) -> dict[str, Any]:
    resolved_target = target or DEFAULT_TARGET
    tools = {
        "space": lambda: get_space(),
        "get_host_workload": lambda: get_host_workload(resolved_target),
        "get_host_cpu": lambda: get_host_cpu(resolved_target),
        "get_host_system_env": lambda: get_host_system_env(resolved_target),
        "get_host_disk": lambda: get_host_disk(resolved_target),
        "get_host_inode": lambda: get_host_inode(resolved_target),
        "get_disk_io": lambda: get_disk_io(resolved_target),
        "get_top_processes": lambda: get_top_processes(resolved_target),
    }
    if tool_name not in tools:
        return {
            "tool": tool_name,
            "target": resolved_target,
            "success": False,
            "summary": "unknown tool",
            "metrics": {"available_tools": sorted(tools)},
        }
    return tools[tool_name]()
