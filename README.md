# AIOps MCP Analyzer

一个可部署到服务器上的轻量 AIOps 诊断应用：

- `server.py`：HTTP 后端，提供页面和分析 API。
- `aliyun_ops_mcp.py`：MCP SSE 服务，供 Agent 调用补查工具。
- `ops_core.py`：巡检、补查证据和规则分析核心逻辑。
- `web/`：截图风格的前端页面。

## 本地启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8080
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\start_api.ps1
```

打开：

```text
http://localhost:8080
```

## MCP 服务启动

```bash
python aliyun_ops_mcp.py
```

默认监听：

```text
http://0.0.0.0:8000/sse
```

`.vscode/mcp.json` 可以配置为：

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

## API

完整分析：

```bash
curl -X POST http://localhost:8080/api/analyze/full \
  -H "Content-Type: application/json" \
  -d '{"target":"192.168.145.172","space_code":"bkcc__131","source":"space_list"}'
```

启用 DeepSeek LLM 归因：

```bash
cp .env.example .env
vim .env
```

`.env` 内容：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

然后重启服务：

```bash
systemctl restart aiops-api
```

或手动启动：

```bash
./start_api.sh
```

调用：

```bash

curl -X POST http://localhost:8080/api/analyze/full \
  -H "Content-Type: application/json" \
  -d '{"target":"192.168.145.172","space_code":"bkcc__131","source":"space_list","use_llm":true}'
```

生产环境不要把 `.env` 提交到仓库，项目的 `.gitignore` 已经默认忽略 `.env`。

返回结构：

```json
{
  "target": "192.168.145.172",
  "generated_at": 1780300000,
  "actions": [],
  "evidence": []
}
```

## 服务器部署建议

1. 将项目上传到服务器，例如 `/opt/aiops-mcp-analyzer`。
2. 安装 Python 3.11+。
3. 执行 `pip install -r requirements.txt`。
4. 启动 HTTP 服务：`PORT=8080 ./start_api.sh`。
5. 如需 Agent 使用 MCP，再启动：`./start_mcp.sh`。
6. 在安全组或防火墙中开放前端/API 端口 `8080`，MCP 端口 `8000` 建议仅内网开放。

生产环境建议用 systemd 托管。

`/etc/systemd/system/aiops-api.service`：

```ini
[Unit]
Description=AIOps Analyzer API
After=network.target

[Service]
WorkingDirectory=/opt/aiops-mcp-analyzer
ExecStart=/opt/aiops-mcp-analyzer/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/aiops-mcp.service`：

```ini
[Unit]
Description=AIOps MCP SSE Server
After=network.target

[Service]
WorkingDirectory=/opt/aiops-mcp-analyzer
ExecStart=/opt/aiops-mcp-analyzer/.venv/bin/python aliyun_ops_mcp.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用：

```bash
systemctl daemon-reload
systemctl enable --now aiops-api aiops-mcp
```

## 作者

zentrix566

## License

MIT
