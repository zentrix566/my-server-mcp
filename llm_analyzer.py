from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


def _compact_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for item in evidence:
        metrics = item.get("metrics") or {}
        compact.append(
            {
                "tool": item.get("tool"),
                "target": item.get("target"),
                "success": item.get("success"),
                "summary": item.get("summary"),
                "metrics": metrics,
            }
        )
    return compact


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response does not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def build_prompt(target: str, evidence: list[dict[str, Any]], rule_actions: list[dict[str, Any]]) -> str:
    payload = {
        "target": target,
        "rule_actions": rule_actions,
        "evidence": _compact_evidence(evidence),
    }
    return (
        "你是一个资深 Linux SRE 和 AIOps 告警归因专家。"
        "请只基于输入的 MCP 补查证据做归因，不要编造未出现的数据。"
        "如果证据不足，要明确说明证据不足，并给出下一步补采建议。"
        "请输出严格 JSON，不要输出 Markdown。JSON 结构必须是："
        "{"
        '"summary": "一句话总览",'
        '"root_cause": "最可能根因或证据不足说明",'
        '"confidence": 0.0,'
        '"actions": ['
        "{"
        '"priority": "立即|中|低",'
        '"level": "critical|warning|normal",'
        '"title": "处置标题",'
        '"eta": "10min|30min|60min",'
        '"reason": "证据依据",'
        '"suggestion": "具体处置步骤"'
        "}"
        "]"
        "}。"
        "下面是输入数据：\n"
        f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def analyze_with_deepseek(
    target: str,
    evidence: list[dict[str, Any]],
    rule_actions: list[dict[str, Any]],
    timeout: int = 30,
) -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return {
            "enabled": False,
            "success": False,
            "error": "DEEPSEEK_API_KEY is not set",
            "summary": "",
            "root_cause": "",
            "confidence": 0.0,
            "actions": rule_actions,
        }

    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    prompt = build_prompt(target, evidence, rule_actions)

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的运维告警归因助手，只输出可解析 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        actions = parsed.get("actions") or rule_actions
        return {
            "enabled": True,
            "success": True,
            "error": "",
            "provider": "deepseek",
            "model": model,
            "summary": str(parsed.get("summary") or ""),
            "root_cause": str(parsed.get("root_cause") or ""),
            "confidence": float(parsed.get("confidence") or 0.0),
            "actions": actions,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "success": False,
            "error": str(exc),
            "provider": "deepseek",
            "model": model,
            "summary": "",
            "root_cause": "",
            "confidence": 0.0,
            "actions": rule_actions,
        }
