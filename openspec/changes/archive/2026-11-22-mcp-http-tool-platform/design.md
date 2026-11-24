## Context

当前 MCP 实现来自未归档变更 `agent-mcp-internet-search`：MCP server 以 stdio 长驻子进程运行在 `backend/app/mcp/`，`backend/app/services/agent/mcp_client.py` 通过 stdio 连接，单一内置工具 `duckduckgo_search`，无服务器登记/发现治理、无令牌、无持久化调用记录、无 `工具@服务器` 引用、QA 为非流式同步返回。其 design 决策 1 明确选择 stdio 并把 HTTP 列为「徒增攻击面」的备选。

课程第 6 课要求的是 HTTP JSON-RPC 多服务器工具平台。本变更推翻该传输决策并补齐治理层。详见 proposal.md 与 specs/mcp-tool-platform。

**前置依赖**：`agent-mcp-internet-search` 尚未归档，其 `agent-tools` / `assistant-qa` / `notification-intake` delta 未进入主 spec。本变更的 `assistant-qa`、`notification-intake` delta 以「该变更已归档」为基线撰写（MODIFIED 其工具调用相关 requirement）。apply 前须先归档 `agent-mcp-internet-search`，否则两套 delta 会在同 capability 上重叠。tasks 将归档列为 Task 0。

## Goals / Non-Goals

**Goals:**
- 独立 `mcp-server/` 工程以 HTTP JSON-RPC 2.0（`POST /mcp` + `GET /health`）暴露 ≥2 工具，`MCP_AUTH_TOKEN` 鉴权，docker-compose 同网部署。
- 宿主按用户隔离地登记/连接/发现/断开工具服务器，令牌只存服务端不回传。
- 技能以 `工具名@服务器名` 声明工具，保存前三校验（格式/清单/连接），运行时最小权限投喂。
- AgentLoop 增加结果安全检查（指令式丢弃、过长截断）、累计调用上限、流式 meta 调用事件与「被拒」状态、持久化调用记录。
- QA 与通知解析升级为流式并接入上述编排，时间确定性约束不变。
- 新增接口 OpenAPI 描述、`apitest/` 端到端用例与 `run_all.py`。

**Non-Goals:**
- 不引入任意 URL 抓取或通用 HTTP 请求工具（违反 SEC-10）。
- 不引入修改型工具（写待办/发通知仍走人工确认，AI-02）。
- 不改变 RAG 检索、时间解析确定性换算、通知确认原子性等既有行为。
- 不实现多 agent 协作、记忆机制或跨用户工具共享。
- 不引入全局「教师」角色体系（见 Open Questions）。

## Decisions

### 决策 1：MCP 传输改为 HTTP JSON-RPC，独立 mcp-server 工程

**选择**：在项目根新建 `mcp-server/` 独立工程（自有 `Dockerfile`、`requirements.txt`、入口），使用官方 `mcp` SDK 的 HTTP transport 或自建轻量 JSON-RPC 端点，暴露 `POST /mcp`（处理 `initialize`/`tools/list`/`tools/call`）与 `GET /health`。`docker-compose.yml` 新增 `mcp-server` 服务，与 `api` 同默认网络互通；主应用通过环境变量 `MCP_TOOL_SERVER_BASE_URL`（如 `http://mcp-server:8090`）连接。移除 `backend/app/mcp/` 的 stdio server 与 `mcp_client.py` 的 stdio 连接逻辑。

**理由**：课程硬性要求 HTTP 单入口与独立服务、Base URL 连接、同网互通（对应 spec「HTTP MCP 工具服务协议与鉴权」）。stdio 子进程无法被外部登记/发现，也无法满足「同伴用你的服务器标识访问」的隔离验证。

**备选**：保留 stdio 仅在宿主内模拟——不满足课程「登记地址指向 Compose 里自建的服务」与「服务单独可验」。

### 决策 2：令牌鉴权与保密

**选择**：`mcp-server` 从环境变量 `MCP_AUTH_TOKEN` 读取令牌，校验 `Authorization: Bearer <token>` 或 JSON-RPC 报文头；无令牌/错令牌返回 JSON-RPC error。宿主侧用户登记的第三方服务器令牌以**对称加密**存储（加密密钥来自环境变量，不入库），`tool_servers` 表响应只返回 `has_token: bool`，调用时解密使用。日志、错误响应、镜像层均不含令牌（SEC-08、SEC-14、BE-12、BE-16）。

**理由**：课程明确「令牌不写进代码、不进镜像层、不进前端」「响应只回是否已配置令牌标记」。

### 决策 3：工具服务器治理模型——owner 隔离 + 连接状态机

**选择**：新增 `tool_servers` 表（DATA-01/02/03）：`id, owner_id, name, base_url, token_cipher, has_token, status(unconnected|connected|error), discovered_tools(jsonb), last_error, created_at, updated_at`。`status` 状态机：登记→`unconnected`；连接成功→`connected` 并整体替换 `discovered_tools`；任一步失败→`error` 并写 `last_error`，不更新清单。断开→`unconnected` 且清空 `discovered_tools`。所有查询按 `owner_id` 过滤，非所有者访问按 404（SEC-01、SEC-02、BE-04）。

**理由**：课程「连接两步失败停在未连接」「断开清空且连两次不翻倍」「同伴看不到你的服务器」均靠此模型满足。owner 隔离复用项目既有授权哲学，无需引入新角色。

### 决策 4：技能（Skill）配置与保存前三校验

**选择**：新增 `skills` 表：`id, owner_id, name, capability(enum: qa|notification_extraction), tool_refs(jsonb 数组), version, created_at, updated_at`。`tool_refs` 元素形如 `"duckduckgo_search@my-server"`。保存时业务层校验（BE-05）：①格式匹配 `^[a-z][a-z0-9_]*@[a-z][a-z0-9-]*$`；②解析出的服务器属于当前用户且 `status=connected`；③工具名在该服务器 `discovered_tools` 内。任一条失败返回 `BUSINESS_*` 422 + 可读原因（BE-04）。

**理由**：课程「保存前校验三条」「工具名小写开头不含连字符、服务器名可含连字符」。技能是课程「保存引用了…的技能 → 会话提问 → 记录成功」端到端用例的载体。

### 决策 5：运行时编排——最小工具集 + 宿主校验 + 结果检查 + 流式 meta

**选择**：`AgentLoop`（重构 `backend/app/services/agent/loop.py`）入参增加「已解析的工具引用列表」。运行时：①按引用从对应已连接服务器取工具定义（名称/说明/输入结构），组成最小 OpenAI tools schema（不再 `list_tools` 全量投喂）；②模型返回 `tool_calls` 后，宿主按输入结构校验参数，校验通过才带令牌调 `tools/call`，否则记 `rejected` 不发请求（AI-02、SEC-11）；③结果经检查器：命中指令式正则（如「忽略以上」「读取密钥」「执行」）整条丢弃，超过 `TOOL_RESULT_MAX_CHARS` 截断（AI-08、SEC-09）；④通过检查的结果作为 `tool` 消息回注；⑤循环受 `AGENT_MAX_TOOL_ITERATIONS`（轮次）与 `AGENT_MAX_TOTAL_TOOL_CALLS`（累计）双上限，超限优雅降级返回已有上下文（AI-05）。

流式：QA 与通知解析接口改为 SSE（`text/event-stream`），先推送 `meta` 事件（含本次 `tool_calls` 的 `{tool@server, status}`，status ∈ success/rejected/error），再推送正文分片。未连接或越权调用在 meta 中标记 `rejected`，不静默成功（对应 spec「流式调用事件与 meta」）。

### 决策 6：调用记录持久化

**选择**：新增 `tool_call_records` 表（只增不改，DATA-03）：`id, owner_id, tool_name, server_name, server_id(nullable), result(enum: success|rejected|error), conversation_id, round_index, triggered_by(user_id), duration_ms, created_at`。`server_id` 允许 null：调用时若服务器已被改名/删除则解析不到归属，`server_id` 置 null 且**不写记录**（对应 spec「服务器删除不写记录」）。查询接口默认 `page_size=20` 上限 100（BE-09），按 `owner_id` 过滤。记录不含工具返回正文或用户问题全文（SEC-14、AI-10）。

### 决策 7：与 agent-mcp-internet-search 的迁移

**选择**：apply 顺序为「归档 `agent-mcp-internet-search` → apply 本变更」。本变更实施时移除 `backend/app/mcp/` 的 stdio server 模块与 `mcp_client.py` 的 stdio 连接，`AgentLoop` 改为注入 HTTP 解析后的工具集；`duckduckgo_search` 工具迁移到 `mcp-server/` 并新增第 2 个工具。`config.py` 移除 `MCP_SERVER_MODULE`，新增 `MCP_TOOL_SERVER_BASE_URL`、`MCP_SERVER_TOKEN_ENCRYPT_KEY`、`AGENT_MAX_TOTAL_TOOL_CALLS`、`TOOL_RESULT_MAX_CHARS`。`.env.example` 同步更新。

### 决策 8：接口与文档

**选择**：新增 REST 路由（BE-02 命名）：
- `POST/GET /api/v1/tool-servers`、`GET/PATCH/DELETE /api/v1/tool-servers/{id}`、`POST /api/v1/tool-servers/{id}/connect`、`POST /api/v1/tool-servers/{id}/disconnect`、`GET /api/v1/tool-servers/{id}/tools`
- `POST/GET /api/v1/skills`、`GET/PATCH/DELETE /api/v1/skills/{id}`
- `GET /api/v1/tool-call-records`
- `POST /api/v1/qa/ask` 与通知解析改为流式

FastAPI 默认 `/docs` 已启用（main.py 未关闭），新增路由的 Pydantic 模型自动生成 OpenAPI；为关键接口补 `description`/`responses` 与错误码（BE-03、BE-04）。

### 决策 9：测试分层

**选择**：①后端 pytest（`backend/tests/`）补充服务器治理、技能三校验、记录隔离、流式降级、结果检查用例；②新建根级 `apitest/`（课程要求风格），用 `requests` 打真实运行中的服务，覆盖登记/连接/列工具/断开/非所有者被拒 + 一条端到端（连接→保存技能→提问→记录成功）；③`run_all.py` 一键执行全部 apitest 并生成 HTML 报告（报告不入库，TEST 规范）。

## Risks / Trade-offs

- **[与未归档变更重叠]** → apply 前必须先归档 `agent-mcp-internet-search`；若未归档，两套 delta 在 `assistant-qa`/`notification-intake` 冲突。Task 0 强制归档并校验。
- **[HTTP 传输增加攻击面]** → `mcp-server` 仅在 compose 内网暴露，令牌鉴权；不映射宿主端口到公网（OPS）。令牌强随机，错令牌返回统一错误不枚举。
- **[mcp SDK HTTP transport 成熟度]** → 若官方 SDK 的 streamable-http 传输不稳定，自建轻量 JSON-RPC 2.0 端点（仅需三个方法），控制依赖（SEC-16）。
- **[流式改造回归]** → QA/通知解析从同步改 SSE，前端需配套消费；保留非流式降级或前端适配，避免现有页面白屏（TEST 回归覆盖）。
- **[令牌加密存储]** → 加密密钥丢失将无法调用已登记服务器；提供重新输入令牌的入口，不依赖可逆恢复。
- **[第二个工具的选择]** → 课程示范 `formula_hint`/`unit_convert`，任选其一或实现更贴切的纯计算工具（无外部依赖、无密钥），不影响架构。

## Migration Plan

1. **Task 0**：归档 `agent-mcp-internet-search`（`openspec archive`），确认主 spec 含 `agent-tools` 及 QA/通知解析工具调用 requirement。
2. 新增依赖与配置：`mcp-server/` 工程、`requirements.txt`、`.env.example`（`MCP_AUTH_TOKEN` 等）。
3. 数据迁移：alembic 新增 `tool_servers`/`skills`/`tool_call_records` 表（DATA-04），更新 `docs/data-dictionary.md`（DATA-05）。
4. 实现 `mcp-server`（HTTP 三方法 + /health + 令牌 + ≥2 工具），docker-compose 新增服务。
5. 实现宿主：models/repositories/services/apis（服务器治理、技能、记录），按 BE/SEC/DATA 规则。
6. 重构 `AgentLoop` 与 `mcp_client`（HTTP 化、最小集、结果检查、双上限、流式 meta）。
7. 改造 QA/通知解析为流式并接入编排，保持时间确定性。
8. 补 OpenAPI 描述、`apitest/` 与 `run_all.py`；后端 pytest 补全。
9. `docker compose up -d --build` 重建，端到端验证；回滚：移除新服务与路由，恢复 stdio（已归档版本）。

## Open Questions

- **全局「教师/管理」角色**：课程多处提「管理角色（教师）」「非管理角色应被拒」。项目当前 `users` 表无角色字段。本设计采用「工具服务器/技能/记录均为 owner 私有资源，所有者即管理者，非所有者访问 404」来等价满足隔离与「被拒」要求，暂不引入全局 admin。若课程验收强制要求显式角色字段，需额外在 `users` 加 `role` 并加角色中间件——这会改变数据模型与 spec，建议在评审时确认是否需要。
- **第二个工具的具体实现**：选 `formula_hint`、`unit_convert` 还是其他纯函数工具？不影响架构与 spec，实施时定。
- **流式协议**：SSE 还是 chunked JSON？倾向 SSE（前端 EventSource 友好），实施时确认与现有前端 axios 封装的兼容方式。
