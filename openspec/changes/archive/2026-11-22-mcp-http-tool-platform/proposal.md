## Why

课程第 6 课「MCP 与工具接入」要求交付一个可登记的 HTTP MCP 工具平台：独立 `mcp-server/` 服务以 JSON-RPC 2.0 暴露工具、宿主侧登记/连接/发现/断开多台工具服务、技能用 `工具名@服务器名` 声明工具并校验、调用可观测记录、流式 meta 推送调用事件，以及 Swagger 文档与 `apitest` 端到端用例。

当前项目的 MCP 实现（来自未归档变更 `agent-mcp-internet-search`）走 **stdio 长驻子进程 + 单一内置工具**：无独立 `mcp-server/`、无 HTTP 端点、无令牌鉴权、无服务器登记与工具发现治理、无持久化调用记录、无 `工具@服务器` 引用与流式 meta。架构与课程要求系统性不符，需要重构传输层并补齐平台治理能力。

## What Changes

- **BREAKING**：将 MCP 运行时从 stdio 子进程重构为 **HTTP JSON-RPC 2.0**（`POST /mcp` + `/health`），独立 `mcp-server/` 工程由 `docker-compose.yml` 同网构建启动，主应用通过 Base URL 连接。
- MCP 工具服务从环境变量 `MCP_AUTH_TOKEN` 读取令牌鉴权，无令牌/错令牌拒绝并返回可读 JSON-RPC 错误；工具扩至 **≥2 个**（保留 `duckduckgo_search`，新增如 `formula_hint` 或 `unit_convert` 这类贴切工具），每个写全名称/说明/输入结构。
- 宿主新增**工具服务器治理**：登记（名称、Base URL、令牌只存服务端、响应只回「是否已配置令牌」标记）、连接（握手 `initialize` + 发现 `tools/list` 两步，失败停在未连接并给可读原因，成功才整体替换清单）、断开（清空清单且不可再调用，连两次不翻倍）、列表查询。
- 引入**技能（Skill）配置**：每个技能关联能力（qa / notification_extraction），工具项支持 `工具名@服务器名` 引用；保存前校验格式、工具是否在已连接服务器的发现清单内、服务器是否已连接，任一条不满足即拒绝。
- **调用编排升级**：按技能声明的最小工具集传给模型（不再全量投喂）；工具返回结果先过检查（命中指令式句式整条丢弃、过长截断）再作为工具消息回注；循环设轮次上限与累计调用次数上限，超限优雅降级用已有信息作答；未连接或越权调用记为「被拒」。
- **流式响应**：调用事件先于正文推送，流式 meta 中可见本次用到的工具及状态（成功/被拒/出错）。
- **调用记录持久化**：每次调用留一条只增不改的记录，覆盖「调了什么（tool@server）、结果、谁触发、哪次对话第几轮、什么时候」；管理界面可查询自己范围内的记录，默认带条数上限；服务器改名/删除时该次调用无处归属不写记录。
- **授权隔离**：工具服务器、技能、调用记录均按所有者隔离，非所有者访问返回 404（与不存在一致）；主路径继续沿用 Bearer 认证、范围只取自会话、跨范围按「不存在」处理。
- 补齐本课新增接口的 OpenAPI 描述，浏览器可打开 Swagger 试调；新增 `apitest/` 用例（登记/连接/列工具/断开/非所有者被拒）与一条端到端用例，`run_all.py` 一键跑并生成 HTML 报告。

## Capabilities

### New Capabilities

- `mcp-tool-platform`: HTTP MCP 工具服务与多服务器治理平台——独立工具服务的协议/鉴权/健康检查、服务器登记连接发现断开、技能工具引用与保存校验、最小权限工具集编排、结果检查与循环上限降级、流式 meta 调用事件、持久化调用记录与范围隔离。

### Modified Capabilities

- `assistant-qa`: 问答助手的工具调用从「全量投喂已登记工具」改为「按技能声明的最小工具集」，新增流式 meta 推送调用事件与状态、结果安全检查、超限优雅降级；搜索不可用时仍降级为仅本地资料回答（行为不变）。
- `notification-intake`: 通知解析接入技能声明的工具集编排与结果检查、流式 meta；时间字段仍完全由可信时间上下文与确定性规则生成，工具结果不得参与时间基准判定（约束不变）。

> 与 `agent-mcp-internet-search` 的关系：本变更重构其引入的 stdio `agent-tools` 运行时为 HTTP 多服务器平台，并扩展治理、记录与流式能力。该变更目前未归档，建议在 apply 本变更前先归档它作为基线；若未归档，apply 时需按本变更 design 的迁移路径移除 stdio 实现，避免两套运行时并存。

## Impact

- **代码**：新增根级 `mcp-server/` 独立工程（含 `Dockerfile`、`/mcp`、`/health`、≥2 工具）；新增后端 `app/services/mcp/`（HTTP client、服务器/技能/调用记录的 service 与 repository）、`app/api/v1/` 下工具服务器与技能路由、`app/models/` 下 `tool_server`/`skill`/`tool_call_record` 模型与 alembic 迁移；重构 `app/services/agent/` 与 `app/mcp/`（stdio 实现移除或迁移）。
- **接口**：新增 `/api/v1/tool-servers`（CRUD + connect + disconnect + tools）、`/api/v1/skills`（CRUD + 校验）、`/api/v1/tool-call-records`（查询）；`/qa/ask` 与通知解析改为流式并带 meta。
- **依赖**：`mcp` SDK 的 HTTP transport（或自建 JSON-RPC 客户端）；`mcp-server/` 新增 `fastapi`/`uvicorn`（若独立于主后端）。
- **配置**：`.env.example` 新增 `MCP_AUTH_TOKEN`、`MCP_SERVER_BASE_URL`、`AGENT_MAX_TOTAL_TOOL_CALLS`、工具结果截断长度等；主后端不再需要 `MCP_SERVER_MODULE`。
- **运维**：`docker-compose.yml` 新增 `mcp-server` 服务，与 `api` 同网；健康检查指向 `/health`。
- **安全**：令牌只存服务端不回传、不进日志/镜像/前端；工具结果按外部不可信内容处理（SEC 边界）；调用记录不含工具返回正文或用户问题全文。
- **测试**：新增 `apitest/` 与 `run_all.py`；后端 pytest 补充服务器治理、技能校验、记录隔离、流式降级用例。
