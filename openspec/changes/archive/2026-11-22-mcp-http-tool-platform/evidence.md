# 验收证据 — mcp-http-tool-platform

本文件记录课程第七部分要求的验收项与同伴交叉验证项的复现命令、实际结果与证据位置。不包含密钥、令牌字面量或资料正文。

## 复现环境

- 后端虚拟环境：`backend/.venv`（Python 3.11）。
- Docker Desktop 已启动，守护进程就绪（`docker info` 成功）。
- 本地 `.env` 已含 `MCP_AUTH_TOKEN` / `MCP_SERVER_TOKEN_ENCRYPT_KEY` 等新增项（从 `.env.example` 同步），且 `.env` 被 `.gitignore` 忽略（`git check-ignore .env` → `.env`），不会提交真实密钥。

## 10.3 验收证据（五项）

### ① 健康检查 + 带令牌 tools/list + tools/call

- 命令：`docker compose ps` → `pa_mcp_server` 状态 `Up (healthy)`（健康检查命中 `GET /health`）。
- 命令（容器内直接调用，验证令牌与工具返回）：
  ```bash
  docker compose exec -T api python -c "..."  # POST http://mcp-server:8090/mcp tools/call unit_convert
  ```
- 实际结果：返回文本 `{"value": 10.0, "from_unit": "m", "to_unit": "ft", "result": 32.808398950131235}`。
- 证据位置：本会话执行日志；`apitest/report.html` 端到端用例「QA SSE：success 调用在 meta 可见」。

### ② 端到端：连接 → 发现 → 绑定 → 触发 → 记录含 tool@server

- 离线一键（隔离 SQLite + stub LLM + 真实 mcp-server 子进程）：
  ```bash
  cd backend && .\.venv\Scripts\python.exe ..\apitest\run_all.py
  ```
- 实际结果：46 项检查全部通过，退出码 0；报告 `apitest/report.html`。
- 记录落库（直接读库确认）：`raw_results=['error','rejected','success']`，`count=4`，含 `unit_convert@good`（success）、`boom@bad`（error）、`unit_convert@good`（rejected）。
- 活体全栈冒烟（重建后的 Docker 栈）：注册→登录→登记 base_url=`http://mcp-server:8090`→连接→`status=connected`，`tools=[duckduckgo_search, unit_convert]`。
- 证据位置：`apitest/report.html`；本会话活体冒烟日志。

### ③ 断开后用其工具的技能：保存或调用路径被拒

- 保存路径：`apitest/cases.py` 边界用例「引用未连接服务器 -> BUSINESS_RULE 422」通过。
- 调用路径（运行时断开）：`backend/tests/test_sse_streaming.py` 用例「未连接服务器 meta 显示 rejected 且主路径不阻断」通过。
- 证据位置：`apitest/report.html`（边界组）；`backend/tests/test_sse_streaming.py`。

### ④ 调小上限后超限优雅降级

- 证据位置：`backend/tests/test_agent_tools.py`（双上限用例：`AGENT_MAX_TOOL_ITERATIONS` / `AGENT_MAX_TOTAL_TOOL_CALLS` 到顶后停止并返回降级回答，不报错）。全量 `pytest` 通过。

### ⑤ 令牌未出现在前端 / 代码 / 镜像

- 列表/详情响应不回传：`apitest/report.html`「列表含已连接服务器且不回传令牌」断言响应全文不含 `token_cipher`/`token`，通过。
- 镜像层无令牌字面量：`docker inspect teamproject-mcp-server --format '{{.Config.Env}}'` 不含 `TOKEN`；`mcp-server/Dockerfile` grep `TOKEN|secret` 无命中。
- 代码无令牌字面量：令牌仅从 `os.environ` 读取（`mcp-server/app/main.py`）；后端存储用 `MCP_SERVER_TOKEN_ENCRYPT_KEY` 派生的 Fernet 密文（`backend/app/core/crypto.py`）。
- 前端不展示令牌：`frontend/src/api/client.ts` 仅传 Bearer，不渲染服务器令牌。

## 10.4 同伴交叉验证（四项，各含可复现步骤）

1. **服务隔离**：`apitest/cases.py` 失败用例「非所有者 GET/连接/删除返回 404 与不存在一致」→ 全部 PASS。复现：`cd backend && .\.venv\Scripts\python.exe ..\apitest\run_all.py --case 失败`。
2. **令牌不回传**：见 10.3 ⑤。复现：`GET /api/v1/tool-servers` 响应中不存在 `token`/`token_cipher` 字段。
3. **断开即失效**：`POST /api/v1/tool-servers/{id}/disconnect` 后 `discovered_tools` 清空、`status=unconnected`；引用其工具的技能保存被拒（10.3 ③）。
4. **记录只看自己范围**：`apitest/cases.py` 端到端用例「记录按 owner 隔离：其他用户查不到」→ PASS（`other_count=0`）。

## 构建与回归（10.1 / 10.2）

- 后端全量：`cd backend && .\.venv\Scripts\python.exe -m pytest tests/ -q` → **138 passed**，退出码 0。
- 全栈重建：`docker compose up -d --build` → 5 个镜像构建成功，`pa_db`/`pa_mcp_server` healthy，`pa_api`/`pa_web`/`pa_worker` running。
- 迁移：`docker compose exec -T api alembic current` → `0016_mcp_tool_platform (head)`；`pa_db` 中 `\dt tool_servers` 存在。
- compose 配置：`docker compose config --quiet` → 退出码 0；`docker compose config --services` 含 `mcp-server`。

## 未执行 / 不适用

- 真实模型评测未运行（无模型配置时按演示模式），不声称模型效果已验证；工具平台行为由离线 stub LLM 覆盖，时间字段生成不受工具影响（`test_sse_streaming.py` 断言带工具与不带工具时间字段一致）。
- 浏览器人工验收不在自动化范围；前端类型检查 `vue-tsc -b` 通过（Task 7）。
