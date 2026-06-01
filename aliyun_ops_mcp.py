from __future__ import annotations

from fastmcp import FastMCP

from ops_core import (
    DEFAULT_TARGET,
    find_large_log_files as core_find_large_log_files,
    get_disk_io as core_get_disk_io,
    get_host_cpu as core_get_host_cpu,
    get_host_disk as core_get_host_disk,
    get_host_inode as core_get_host_inode,
    get_host_system_env as core_get_host_system_env,
    get_host_workload as core_get_host_workload,
    get_space as core_get_space,
    get_top_processes as core_get_top_processes,
    run_full_analysis as core_run_full_analysis,
)

mcp = FastMCP("aliyun-ops")


@mcp.tool()
def space(space_code: str = "bkcc__131", source: str = "space_list"):
    """查询当前空间/权限上下文。"""
    return core_get_space(space_code=space_code, source=source)


@mcp.tool()
def get_host_workload(target: str = DEFAULT_TARGET):
    """查询主机负载，包括 load1/load5/load15 和单核负载。"""
    return core_get_host_workload(target)


@mcp.tool()
def get_host_cpu(target: str = DEFAULT_TARGET):
    """查询主机 CPU 使用率、user/system/iowait/idle。"""
    return core_get_host_cpu(target)


@mcp.tool()
def get_host_system_env(target: str = DEFAULT_TARGET):
    """查询运行进程、I/O 等待进程、内存和 swap 等系统环境信息。"""
    return core_get_host_system_env(target)


@mcp.tool()
def get_host_disk(target: str = DEFAULT_TARGET):
    """查询磁盘挂载点容量和使用率。"""
    return core_get_host_disk(target)


@mcp.tool()
def get_host_inode(target: str = DEFAULT_TARGET):
    """查询磁盘 inode 使用情况。"""
    return core_get_host_inode(target)


@mcp.tool()
def get_disk_io(target: str = DEFAULT_TARGET):
    """查询磁盘 I/O 累计读写计数器。"""
    return core_get_disk_io(target)


@mcp.tool()
def get_top_processes(target: str = DEFAULT_TARGET, limit: int = 10):
    """查询 CPU/内存占用最高的进程。"""
    return core_get_top_processes(target, limit=limit)


@mcp.tool()
def find_large_log_files(target: str = DEFAULT_TARGET, limit: int = 10):
    """查询 /var/log 下最大的日志文件。"""
    return core_find_large_log_files(target, limit=limit)


@mcp.tool()
def analyze_host(
    target: str = DEFAULT_TARGET,
    space_code: str = "bkcc__131",
    source: str = "space_list",
    use_llm: bool = False,
):
    """执行一次完整补查并生成处置建议。"""
    return core_run_full_analysis(target=target, space_code=space_code, source=source, use_llm=use_llm)


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
