# AIOps MCP Analyzer

AIOps MCP Analyzer 是一个可部署在 Linux 服务器上的轻量级运维诊断应用。它把本机巡检、MCP 工具补查、规则分析、DeepSeek LLM 归因和 Web 可视化页面串成一条完整链路。

核心流程：

```text
服务器指标采集
  -> MCP 补查证据
  -> 规则分析
  -> DeepSeek LLM 归因
  -> Web 页面展示处置建议和证据链
```

## 功能特性

- 主机负载、CPU、内存、磁盘、inode、磁盘 I/O、进程、日志文件巡检。
- 输出结构化 `actions` 处置建议和 `evidence` MCP 补查证据。
- 支持 DeepSeek LLM 归因分析，失败时自动回退到规则分析。
- 提供 Web 页面，展示“处置建议 + MCP 补查证据 + LLM 归因结论”。
- 提供 FastAPI HTTP API，方便前端、脚本或其它系统调用。
- 提供 FastMCP SSE 服务，方便 Agent 通过 MCP 工具调用。
- 支持 `.env` 文件配置 DeepSeek API Key。

## 项目结构

```text
aiops-mcp-analyzer/
├── aliyun_ops_mcp.py      # FastMCP SSE 服务入口，暴露 MCP 工具
├── llm_analyzer.py        # DeepSeek LLM 归因分析模块
├── ops_core.py            # 巡检采集、规则分析、完整分析核心逻辑
├── ops_mcp.py             # MCP 兼容入口，复用 aliyun_ops_mcp.py
├── server.py              # FastAPI 后端，提供 API 和静态页面
├── requirements.txt       # Python 依赖
├── start_api.sh           # Linux/macOS API 启动脚本
├── start_mcp.sh           # Linux/macOS MCP 启动脚本
├── start_api.ps1          # Windows API 启动脚本
├── start_mcp.ps1          # Windows MCP 启动脚本
├── .env.example           # DeepSeek 环境变量示例
├── .gitignore             # 忽略虚拟环境、缓存、日志和 .env
├── web/
│   ├── index.html         # 前端页面结构
│   ├── styles.css         # 前端样式
│   └── app.js             # 前端交互逻辑
└── .vscode/
    └── mcp.json           # 本地 MCP 连接示例
```

## 环境要求

- Python 3.11+
- Linux 服务器建议使用 systemd 托管服务
- 如需 LLM 归因，需要 DeepSeek API Key

检查 Python 版本：

```bash
python3 --version
```

## 安装依赖

```bash
cd /opt/aiops-mcp-analyzer

python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

如果你的虚拟环境叫 `.venv` 也可以，启动脚本会优先使用 `.venv/bin/python`，其次使用 `venv/bin/python`，最后使用当前环境里的 `python`。

## 配置 DeepSeek

复制配置模板：

```bash
cp .env.example .env
vim .env
```

`.env` 示例：

```bash
DEEPSEEK_API_KEY=你的DeepSeekAPIKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

注意：

- 不要把 `.env` 提交到仓库。
- `.env` 已经在 `.gitignore` 中默认忽略。
- 修改 `.env` 后需要重启 API 服务。

## 启动 Web/API 服务

手动启动：

```bash
cd /opt/aiops-mcp-analyzer
source venv/bin/activate
./start_api.sh
```

默认监听：

```text
http://0.0.0.0:8080
```

浏览器访问：

```text
http://服务器IP:8080
```

健康检查：

```bash
curl http://127.0.0.1:8080/api/health
```

## 启动 MCP 服务

手动启动：

```bash
cd /opt/aiops-mcp-analyzer
source venv/bin/activate
./start_mcp.sh
```

默认监听：

```text
http://0.0.0.0:8000/sse
```

MCP 客户端配置示例：

```json
{
  "servers": {
    "aliyunOps": {
      "type": "sse",
      "url": "http://服务器IP:8000/sse"
    }
  }
}
```

## Web 使用方法

打开页面后可以：

1. 输入目标主机。留空时分析当前部署服务器。
2. 输入空间编码，默认 `bkcc__131`。
3. 勾选“DeepSeek 归因”启用 LLM 分析。
4. 点击“全量分析”。
5. 查看处置建议、LLM 归因结论和 MCP 补查证据。

当前版本主要分析部署所在服务器。页面里的目标主机字段会进入结果展示和分析上下文，但远程主机采集还需要后续接入 SSH、Agent、Prometheus 或云监控 API。

## API 使用方法

规则分析：

```bash
curl -X POST http://127.0.0.1:8080/api/analyze/full \
  -H "Content-Type: application/json" \
  -d '{"target":"172.17.107.89","space_code":"bkcc__131","source":"space_list"}'
```

启用 DeepSeek LLM 归因：

```bash
curl -X POST http://127.0.0.1:8080/api/analyze/full \
  -H "Content-Type: application/json" \
  -d '{"target":"172.17.107.89","space_code":"bkcc__131","source":"space_list","use_llm":true}'
```

返回结构示例：

```json
{
  "target": "172.17.107.89",
  "generated_at": 1780361911,
  "actions": [],
  "rule_actions": [],
  "llm": {
    "enabled": true,
    "success": true,
    "provider": "deepseek",
    "model": "deepseek-v4-flash",
    "summary": "",
    "root_cause": "",
    "confidence": 0.95
  },
  "evidence": []
}
```

单工具查询：

```bash
curl http://127.0.0.1:8080/api/tools/get_host_cpu
curl http://127.0.0.1:8080/api/tools/get_host_disk
curl http://127.0.0.1:8080/api/tools/get_top_processes
```

## systemd 部署

生产环境建议使用 systemd 托管 API 和 MCP 服务。

创建 API 服务：

```bash
sudo vim /etc/systemd/system/aiops-api.service
```

内容：

```ini
[Unit]
Description=AIOps Analyzer API
After=network.target

[Service]
WorkingDirectory=/opt/aiops-mcp-analyzer
ExecStart=/opt/aiops-mcp-analyzer/venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

创建 MCP 服务：

```bash
sudo vim /etc/systemd/system/aiops-mcp.service
```

内容：

```ini
[Unit]
Description=AIOps MCP SSE Server
After=network.target

[Service]
WorkingDirectory=/opt/aiops-mcp-analyzer
ExecStart=/opt/aiops-mcp-analyzer/venv/bin/python aliyun_ops_mcp.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aiops-api aiops-mcp
```

查看状态：

```bash
sudo systemctl status aiops-api
sudo systemctl status aiops-mcp
```

重启：

```bash
sudo systemctl restart aiops-api
sudo systemctl restart aiops-mcp
```

## 常见问题

### 页面没有样式

检查静态资源是否存在：

```bash
ls -la web
curl -I http://127.0.0.1:8080/assets/styles.css
```

如果 `styles.css` 返回 404，说明 `web/` 目录没有上传完整，重新上传整个 `web` 目录。

### DeepSeek 返回 401

先直接测试 DeepSeek：

```bash
set -a
source .env
set +a

curl -i https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${DEEPSEEK_API_KEY}" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "只回复 OK"}],
    "stream": false
  }'
```

如果直接请求成功，但页面仍失败，重启 API 服务。

### 修改代码或 .env 后不生效

手动启动时可能有旧进程残留：

```bash
ps -ef | grep "uvicorn server:app" | grep -v grep
pkill -f "uvicorn server:app"
./start_api.sh
```

使用 systemd 时执行：

```bash
sudo systemctl restart aiops-api
```

### 返回中文乱码

确认服务器上的源码是 UTF-8，并且上传的是最新版本：

```bash
grep -n "当前无明显高危异常" ops_core.py
grep -n "权限空间匹配" ops_core.py
```

如果 grep 出来就是乱码，重新上传 UTF-8 源码文件。

## 安全建议

- `8080` Web/API 端口可以按需开放。
- `8000` MCP SSE 端口建议只在内网或可信 IP 范围开放。
- 不要把 `.env`、API Key、Token、日志里的敏感信息提交到仓库。
- 生产环境建议在 Nginx 前面加鉴权或限制来源 IP。

## 作者

zentrix566

## License

MIT
