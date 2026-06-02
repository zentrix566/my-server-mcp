from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from llm_analyzer import analyze_with_deepseek


DEFAULT_TARGET = socket.gethostbyname(socket.gethostname())


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def run_command(args: list[str], timeout: int = 5) -> dict[str, Any]:
    """Run a readonly command and return a stable result shape."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"command not found: {args[0]}", "returncode": 127}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "command timeout", "returncode": 124}


def ok_tool(name: str, target: str, summary: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": name,
        "target": target,
        "success": True,
        "summary": summary,
        "metrics": metrics,
        "checked_at": int(time.time()),
    }


def fail_tool(name: str, target: str, message: str) -> dict[str, Any]:
    return {
        "tool": name,
        "target": target,
        "success": False,
        "summary": message,
        "metrics": {},
        "checked_at": int(time.time()),
    }


def _loadavg() -> tuple[float, float, float]:
    if hasattr(os, "getloadavg"):
        try:
            return os.getloadavg()
        except OSError:
            pass
    return (0.0, 0.0, 0.0)


def _proc_stat_value(key: str) -> int | None:
    stat = Path("/proc/stat")
    if not stat.exists():
        return None
    try:
        for line in stat.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(key):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def _running_process_counts() -> dict[str, int | None]:
    loadavg = Path("/proc/loadavg")
    running = None
    total = None
    if loadavg.exists():
        try:
            parts = loadavg.read_text(encoding="utf-8", errors="ignore").split()
            running_text, total_text = parts[3].split("/")
            running = int(running_text)
            total = int(total_text)
        except (OSError, ValueError, IndexError):
            pass
    return {
        "proc_running_current": running,
        "proc_total_current": total,
        "proc_blocked_current": _proc_stat_value("procs_blocked"),
    }


def get_space(space_code: str = "default", source: str = "local") -> dict[str, Any]:
    return {
        "tool": "space",
        "success": True,
        "summary": f"权限空间匹配：space_code={space_code}，来源={source}",
        "metrics": {
            "space_code": space_code,
            "source": source,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
        },
        "checked_at": int(time.time()),
    }


def get_host_workload(target: str = DEFAULT_TARGET) -> dict[str, Any]:
    load1, load5, load15 = _loadavg()
    cpu_count = psutil.cpu_count() or 1
    per_cpu_load = round(load15 / cpu_count, 2)
    metrics = {
        "load1": round(load1, 2),
        "load5": round(load5, 2),
        "load15": round(load15, 2),
        "cpu_count": cpu_count,
        "per_cpu_load": per_cpu_load,
    }
    return ok_tool(
        "get_host_workload",
        target,
        (
            f"15分钟平均负载(load15)={metrics['load15']}；"
            f"5分钟平均负载(load5)={metrics['load5']}；"
            f"单核CPU负载(per_cpu_load)={per_cpu_load}"
        ),
        metrics,
    )


def get_host_cpu(target: str = DEFAULT_TARGET) -> dict[str, Any]:
    usage = psutil.cpu_percent(interval=0.6)
    times = psutil.cpu_times_percent(interval=0.2)
    metrics = {
        "usage": round(usage, 2),
        "user": round(getattr(times, "user", 0.0), 2),
        "system": round(getattr(times, "system", 0.0), 2),
        "iowait": round(getattr(times, "iowait", 0.0), 2),
        "idle": round(getattr(times, "idle", 0.0), 2),
    }
    return ok_tool(
        "get_host_cpu",
        target,
        (
            f"CPU使用率(usage)={metrics['usage']}%；"
            f"用户态(user)={metrics['user']}%；"
            f"系统态(system)={metrics['system']}%；"
            f"I/O等待(iowait)={metrics['iowait']}%"
        ),
        metrics,
    )


def get_host_system_env(target: str = DEFAULT_TARGET) -> dict[str, Any]:
    counts = _running_process_counts()
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    metrics = {
        **counts,
        "memory_percent": round(virtual.percent, 2),
        "swap_percent": round(swap.percent, 2),
        "boot_time": int(psutil.boot_time()),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
    }
    blocked = metrics.get("proc_blocked_current")
    running = metrics.get("proc_running_current")
    return ok_tool(
        "get_host_system_env",
        target,
        f"运行进程数={running if running is not None else '未知'}；等待I/O进程数={blocked if blocked is not None else '未知'}；内存使用率={metrics['memory_percent']}%",
        metrics,
    )


def get_host_disk(target: str = DEFAULT_TARGET) -> dict[str, Any]:
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (OSError, PermissionError):
            continue
        disks.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / 1024**3, 2),
                "used_gb": round(usage.used / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
                "percent": round(usage.percent, 2),
            }
        )
    disks.sort(key=lambda item: item["percent"], reverse=True)
    top = disks[0] if disks else None
    summary = "未采集到磁盘挂载点" if not top else f"{top['mountpoint']} 使用率={top['percent']}%，剩余={top['free_gb']}GB"
    return ok_tool("get_host_disk", target, summary, {"disks": disks})


def get_host_inode(target: str = DEFAULT_TARGET) -> dict[str, Any]:
    if not hasattr(os, "statvfs"):
        return fail_tool("get_host_inode", target, "当前系统不支持 inode 统计，部署到 Linux 后可自动采集")

    inodes = []
    for part in psutil.disk_partitions(all=False):
        try:
            stat = os.statvfs(part.mountpoint)
        except (OSError, PermissionError):
            continue
        total = stat.f_files
        free = stat.f_ffree
        if not total:
            continue
        used = total - free
        inodes.append(
            {
                "mountpoint": part.mountpoint,
                "total": total,
                "used": used,
                "free": free,
                "percent": round(used / total * 100, 2),
            }
        )
    inodes.sort(key=lambda item: item["percent"], reverse=True)
    top = inodes[0] if inodes else None
    summary = "当前系统不支持 inode 统计" if not top else f"{top['mountpoint']} inode使用率={top['percent']}%"
    return ok_tool("get_host_inode", target, summary, {"inodes": inodes})


def get_disk_io(target: str = DEFAULT_TARGET) -> dict[str, Any]:
    counters = psutil.disk_io_counters(perdisk=True)
    devices = []
    for name, item in counters.items():
        devices.append(
            {
                "device": name,
                "read_mb": round(item.read_bytes / 1024**2, 2),
                "write_mb": round(item.write_bytes / 1024**2, 2),
                "read_count": item.read_count,
                "write_count": item.write_count,
                "busy_time_ms": getattr(item, "busy_time", None),
            }
        )
    return ok_tool("get_disk_io", target, f"采集到 {len(devices)} 个磁盘设备 I/O 计数器", {"devices": devices})


def get_top_processes(target: str = DEFAULT_TARGET, limit: int = 10) -> dict[str, Any]:
    limit = clamp(limit, 1, 30)
    rows = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "cmdline"]):
        try:
            info = proc.info
            rows.append(
                {
                    "pid": info["pid"],
                    "name": info.get("name") or "",
                    "username": info.get("username") or "",
                    "cpu_percent": round(info.get("cpu_percent") or 0.0, 2),
                    "memory_percent": round(info.get("memory_percent") or 0.0, 2),
                    "cmdline": " ".join(info.get("cmdline") or [])[:240],
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda item: (item["cpu_percent"], item["memory_percent"]), reverse=True)
    return ok_tool("get_top_processes", target, f"返回 CPU/内存占用最高的 {min(limit, len(rows))} 个进程", {"processes": rows[:limit]})


def find_large_log_files(target: str = DEFAULT_TARGET, limit: int = 10) -> dict[str, Any]:
    limit = clamp(limit, 1, 50)
    base = Path("/var/log")
    if not base.exists():
        return fail_tool("find_large_log_files", target, "/var/log 不存在，可能不是 Linux 服务器环境")
    files = []
    for path in base.rglob("*"):
        try:
            if path.is_file():
                files.append({"path": str(path), "size_mb": round(path.stat().st_size / 1024**2, 2)})
        except (OSError, PermissionError):
            continue
    files.sort(key=lambda item: item["size_mb"], reverse=True)
    return ok_tool("find_large_log_files", target, f"返回最大的 {min(limit, len(files))} 个日志文件", {"files": files[:limit]})


def collect_evidence(target: str, space_code: str, source: str) -> list[dict[str, Any]]:
    return [
        get_space(space_code=space_code, source=source),
        get_host_workload(target),
        get_host_cpu(target),
        get_host_system_env(target),
        get_host_disk(target),
        get_host_inode(target),
        get_disk_io(target),
        get_top_processes(target, limit=8),
        find_large_log_files(target, limit=8),
    ]


def _metric(evidence: list[dict[str, Any]], tool: str, key: str, default: Any = None) -> Any:
    for item in evidence:
        if item["tool"] == tool:
            return item.get("metrics", {}).get(key, default)
    return default


def _top_disk_percent(evidence: list[dict[str, Any]]) -> tuple[float, str]:
    disks = _metric(evidence, "get_host_disk", "disks", []) or []
    if not disks:
        return 0.0, "/"
    top = disks[0]
    return float(top.get("percent") or 0.0), str(top.get("mountpoint") or "/")


def _relevance_signal(item: dict[str, Any]) -> float:
    tool = item.get("tool")
    metrics = item.get("metrics") or {}

    if not item.get("success", False):
        return 0.25

    if tool == "space":
        return 0.5

    if tool == "get_host_workload":
        load15 = float(metrics.get("load15") or 0.0)
        per_cpu_load = float(metrics.get("per_cpu_load") or 0.0)
        if load15 >= 1 or per_cpu_load >= 1.5:
            return 1.0
        return 0.62

    if tool == "get_host_cpu":
        usage = float(metrics.get("usage") or 0.0)
        iowait = float(metrics.get("iowait") or 0.0)
        if usage >= 80 or iowait >= 10:
            return 1.0
        if usage >= 60 or iowait >= 3:
            return 0.82
        return 0.65

    if tool == "get_host_system_env":
        blocked = int(metrics.get("proc_blocked_current") or 0)
        memory = float(metrics.get("memory_percent") or 0.0)
        swap = float(metrics.get("swap_percent") or 0.0)
        if blocked >= 4 or memory >= 90 or swap >= 60:
            return 1.0
        if memory >= 75 or swap >= 30:
            return 0.78
        return 0.66

    if tool == "get_host_disk":
        disks = metrics.get("disks") or []
        top = max((float(disk.get("percent") or 0.0) for disk in disks), default=0.0)
        if top >= 90:
            return 1.0
        if top >= 80:
            return 0.88
        if top >= 70:
            return 0.74
        return 0.62

    if tool == "get_host_inode":
        inodes = metrics.get("inodes") or []
        top = max((float(inode.get("percent") or 0.0) for inode in inodes), default=0.0)
        if top >= 90:
            return 1.0
        if top >= 80:
            return 0.86
        return 0.56

    if tool == "get_disk_io":
        devices = metrics.get("devices") or []
        return 0.68 if devices else 0.35

    if tool == "get_top_processes":
        processes = metrics.get("processes") or []
        max_cpu = max((float(proc.get("cpu_percent") or 0.0) for proc in processes), default=0.0)
        max_memory = max((float(proc.get("memory_percent") or 0.0) for proc in processes), default=0.0)
        if max_cpu >= 50 or max_memory >= 25:
            return 0.92
        return 0.63

    if tool == "find_large_log_files":
        files = metrics.get("files") or []
        max_size = max((float(file.get("size_mb") or 0.0) for file in files), default=0.0)
        if max_size >= 500:
            return 0.86
        if files:
            return 0.58
        return 0.35

    return 0.5


def score_evidence_relevance(evidence: list[dict[str, Any]], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tool_weights = {
        "space": 55,
        "get_host_workload": 92,
        "get_host_cpu": 95,
        "get_host_system_env": 95,
        "get_host_disk": 92,
        "get_host_inode": 78,
        "get_disk_io": 82,
        "get_top_processes": 82,
        "find_large_log_files": 68,
    }
    has_critical = any(action.get("level") == "critical" for action in actions)
    has_warning = any(action.get("level") == "warning" for action in actions)
    scored = []

    for item in evidence:
        tool = str(item.get("tool") or "")
        base = tool_weights.get(tool, 60)
        signal = _relevance_signal(item)
        score = base * 0.62 + signal * 100 * 0.38
        if not item.get("success", False):
            score = min(score, 45)
        elif has_critical and tool in {"get_host_workload", "get_host_cpu", "get_host_system_env", "get_host_disk"}:
            score = min(100, score + 8)
        elif has_warning and tool in {"get_host_workload", "get_host_cpu", "get_host_disk"}:
            score = min(100, score + 5)

        enriched = dict(item)
        enriched["relevance"] = {
            "score": round(score, 1),
            "label": "high" if score >= 80 else "medium" if score >= 60 else "low",
        }
        scored.append(enriched)

    return scored


def calculate_analysis_confidence(
    evidence: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    llm_result: dict[str, Any],
) -> dict[str, Any]:
    key_tools = {
        "get_host_workload",
        "get_host_cpu",
        "get_host_system_env",
        "get_host_disk",
        "get_host_inode",
        "get_disk_io",
        "get_top_processes",
    }
    successful_key_tools = {
        item.get("tool")
        for item in evidence
        if item.get("tool") in key_tools and item.get("success", False)
    }
    coverage = len(successful_key_tools) / len(key_tools)
    relevance_scores = [
        float((item.get("relevance") or {}).get("score") or 0.0)
        for item in evidence
    ]
    avg_relevance = (sum(relevance_scores) / len(relevance_scores) / 100) if relevance_scores else 0.0

    if any(action.get("level") == "critical" for action in actions):
        rule_confidence = 0.86
    elif any(action.get("level") == "warning" for action in actions):
        rule_confidence = 0.78
    else:
        rule_confidence = 0.72

    llm_confidence = float(llm_result.get("confidence") or 0.0) if llm_result.get("success") else 0.0
    if llm_result.get("success"):
        raw = llm_confidence * 0.50 + coverage * 0.30 + avg_relevance * 0.20
        source = "llm+evidence"
    else:
        raw = rule_confidence * 0.45 + coverage * 0.35 + avg_relevance * 0.20
        source = "rules+evidence"

    score = round(max(0.0, min(raw, 1.0)) * 100, 1)
    return {
        "score": score,
        "label": "high" if score >= 80 else "medium" if score >= 60 else "low",
        "source": source,
        "components": {
            "evidence_coverage": round(coverage * 100, 1),
            "avg_relevance": round(avg_relevance * 100, 1),
            "rule_confidence": round(rule_confidence * 100, 1),
            "llm_confidence": round(llm_confidence * 100, 1),
        },
    }


def analyze_evidence(target: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    load15 = float(_metric(evidence, "get_host_workload", "load15", 0.0) or 0.0)
    per_cpu_load = float(_metric(evidence, "get_host_workload", "per_cpu_load", 0.0) or 0.0)
    cpu_usage = float(_metric(evidence, "get_host_cpu", "usage", 0.0) or 0.0)
    iowait = float(_metric(evidence, "get_host_cpu", "iowait", 0.0) or 0.0)
    blocked = _metric(evidence, "get_host_system_env", "proc_blocked_current", 0)
    disk_percent, mountpoint = _top_disk_percent(evidence)

    if blocked and int(blocked) >= 4 and cpu_usage < 70:
        actions.append(
            {
                "priority": "立即",
                "level": "critical",
                "title": f"排查 {target} I/O 阻塞根因",
                "eta": "10min",
                "reason": f"proc_blocked_current={blocked}，CPU usage={cpu_usage}%，负载与 CPU 不匹配，疑似磁盘 I/O 瓶颈或锁等待。",
                "suggestion": "建议执行 iostat -x 1 查看 util、await、avgqu-sz，结合 lsof、pidstat -d、strace 定位阻塞进程。",
            }
        )

    if disk_percent >= 90:
        actions.append(
            {
                "priority": "立即",
                "level": "critical",
                "title": f"清理 {target} 磁盘空间",
                "eta": "10min",
                "reason": f"{mountpoint} 磁盘使用率已达到 {disk_percent}%。",
                "suggestion": "建议检查 /var/log、/tmp、备份目录，使用 du -sh /* 定位大目录，清理过期日志或临时文件。",
            }
        )
    elif disk_percent >= 80:
        actions.append(
            {
                "priority": "中",
                "level": "warning",
                "title": f"观察 {target} 磁盘空间增长",
                "eta": "30min",
                "reason": f"{mountpoint} 磁盘使用率为 {disk_percent}%，已接近常见告警线。",
                "suggestion": "建议补充日志轮转策略，并确认备份、临时文件和容器镜像的保留周期。",
            }
        )

    if iowait >= 10:
        actions.append(
            {
                "priority": "立即",
                "level": "critical",
                "title": f"对 {target} 设置磁盘 I/O 监控",
                "eta": "30min",
                "reason": f"当前 iowait={iowait}%，可能存在磁盘等待。",
                "suggestion": "建议补采 await、svctm、util、读写吞吐等指标，并配置告警阈值。",
            }
        )
    elif load15 >= 1 and per_cpu_load >= 1.5 and cpu_usage < 65:
        actions.append(
            {
                "priority": "中",
                "level": "warning",
                "title": f"对 {target} 补充负载归因监控",
                "eta": "30min",
                "reason": f"load15={load15}，per_cpu_load={per_cpu_load}，但 CPU usage={cpu_usage}%，需要区分 I/O 等待、锁等待或进程堆积。",
                "suggestion": "建议补充采集进程状态、磁盘 I/O、网络连接和关键服务队列长度。",
            }
        )

    if not actions:
        actions.append(
            {
                "priority": "低",
                "level": "normal",
                "title": f"{target} 当前无明显高危异常",
                "eta": "60min",
                "reason": "基础负载、CPU、磁盘和进程状态未触发高危规则。",
                "suggestion": "建议保留当前巡检频率，并持续补齐业务侧关键指标。",
            }
        )

    return actions[:6]


def run_full_analysis(
    target: str | None = None,
    space_code: str = "bkcc__131",
    source: str = "space_list",
    use_llm: bool = False,
) -> dict[str, Any]:
    resolved_target = target or DEFAULT_TARGET
    evidence = collect_evidence(resolved_target, space_code, source)
    rule_actions = analyze_evidence(resolved_target, evidence)
    llm_result = analyze_with_deepseek(resolved_target, evidence, rule_actions) if use_llm else {
        "enabled": False,
        "success": False,
        "error": "",
        "summary": "",
        "root_cause": "",
        "confidence": 0.0,
        "actions": rule_actions,
    }
    actions = llm_result.get("actions") or rule_actions
    scored_evidence = score_evidence_relevance(evidence, actions)
    confidence = calculate_analysis_confidence(scored_evidence, actions, llm_result)
    return {
        "target": resolved_target,
        "generated_at": int(time.time()),
        "actions": actions,
        "rule_actions": rule_actions,
        "llm": {
            key: value
            for key, value in llm_result.items()
            if key != "actions"
        },
        "confidence": confidence,
        "evidence": scored_evidence,
    }
