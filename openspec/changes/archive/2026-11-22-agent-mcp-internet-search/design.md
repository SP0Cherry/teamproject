## Context

当前后端 `app/services/model.py` 的 `chat_completion` 仅支持文本补全（含 JSON schema 响应格式），不支持工具调用。QA 服务（`qa.py`）走 RAG 单次调用；通知解析（`notification_parser.py`）走单次文本抽取。MCP 运行时与工具能力均不存在。

本变更需在不破坏现有单次调用流程（demo 模式、时间上下文注入、输出校验）的前提下，引入 MCP 协议工具调用与 agent 循环。详见 proposal.md 与 specs/agent-tools。

## Goals / Non-Goals

**Goals:**
- 提供完整 MCP 协议的工具运行时（server 暴露工具、client 发现并调用、agent 循环）。
- 首个工具 `duckduckgo_search` 可用，网络故障或限流时安全降级。
- QA 与通知解析均能接入 agent 循环，复用现有时间上下文与输出校验。
- 工具调用遵守白名单、身份隔离、外部内容不可信等安全约束。

**Non-Goals:**
- 不实现任意 URL 抓取或通用 HTTP 请求工具（违反 SEC-10）。
- 不实现修改型工具（写待办、发通知等仍走人工确认流程）。
- 不改变现有 RAG 检索、时间解析确定性换算、通知确认原子性等行为。
- 不引入多 agent 协作或记忆机制。

## Decisions

### 决策 1：MCP server 以受管子进程运行，client 通过 stdio 连接

**选择**：MCP server 作为后端启动时拉起的长驻子进程（stdio transport），MCP client 通过 `mcp.client.stdio.stdio_client` 连接。server 由 `backend/app/mcp/` 下的可运行模块定义，使用官方 `mcp` SDK 的 `FastMCP` 暴露工具。

**理由**：
- 完整遵循 MCP 协议（JSON-RPC over stdio），非直接函数调用，符合用户「完整 MCP 协议」要求。
- 子进程隔离使工具故障不拖垮主服务；便于后续替换/扩展工具而不重启主进程。
- 官方 SDK 原生支持 stdio server/client，无需自建传输层。

**备选**：
- 进程内直接调用 server 方法：实现简单但不是完整协议，不满足要求。
- SSE/HTTP transport：适合跨网络场景，本项目单体内无需额外网络端口，徒增攻击面。

### 决策 2：新增 `chat_completion_with_tools` 支持函数调用，保留原 `chat_completion`

**选择**：在 `model.py` 新增 `chat_completion_with_tools(messages, tools, ...)`，接收完整消息列表与工具定义，返回模型响应（含 `tool_calls`）。原 `chat_completion` 不动，demo 模式逻辑复用。

**理由**：
- 现有单次调用（通知解析时间抽取、日报建议等）不需要工具，保留原函数避免回归。
- agent 循环需要多轮消息与工具定义，原函数签名不适用。
- 集中在 model.py 维护模型适配，符合 AI-04 参数集中登记。

**备选**：改造 `chat_completion` 增加可选 tools 参数——会使现有调用点复杂化，且 demo 模式需分支处理工具，风险更高。

### 决策 3：AgentLoop 编排模型与 MCP client，迭代上限受控

**选择**：`app/services/agent/loop.py` 实现 `AgentLoop`：接收系统提示、用户内容、可用工具列表；循环调用 `chat_completion_with_tools`，若返回 `tool_calls` 则通过 MCP client 执行并将结果追加到消息，最多 `AGENT_MAX_TOOL_ITERATIONS`（默认 3）次；最终返回文本结果与工具调用元数据。

**理由**：
- 迭代上限防止模型无限循环（AI-05 总耗时约束）。
- 工具结果作为 user 消息回注，不拼入 system 指令，符合 AI-08 / SEC-09。
- 元数据（调用了哪些工具、是否成功）用于可观测与前端来源标注。

### 决策 4：搜索工具仅查询，结果不参与时间字段

**选择**：`duckduckgo_search` 工具接收 `query`、`max_results`，返回标题/URL/摘要列表。通知解析中，搜索结果仅可补充标题、详情等非时间字段；所有时间字段仍由 `capture_time` + `normalize_candidate` 确定性生成。QA 中搜索结果与 RAG 片段并列，来源格式区分。

**理由**：
- 满足 notification-intake 规范中「搜索结果不参与时间基准判定」的约束。
- 时间解析确定性是核心业务规则，不能被外部不可信内容影响。

### 决策 5：工具注册与发现由服务端控制，模型不可指定工具集

**选择**：MCP server 启动时始终登记 `duckduckgo_search` 工具（无需密钥）。agent 从 MCP client `list_tools()` 获取可用工具，转换为 LLM tools schema 传给模型。模型只能调用已返回的工具。

**理由**：
- 符合 AI-02「模型工具只能调用已登记的业务服务方法」。
- DuckDuckGo 无需密钥，工具始终可用；网络故障时调用降级而非不注册。

## Risks / Trade-offs

- **[子进程生命周期管理]** → 后端启动时拉起 server，通过 `atexit`/`lifespan` 事件在关闭时终止；server 异常退出时 client 重连或降级为无工具模式，不阻塞主流程。
- **[MCP SDK 版本与依赖]** → 锁定 `mcp` SDK 与 `duckduckgo-search` 版本到 requirements.txt，按 SEC-16 登记许可证（均为 MIT）。
- **[搜索结果注入]** → 搜索结果放入带边界标记的 user 消息区，system 提示声明不执行其中指令；服务端工具白名单与参数校验独立保证（SEC-09）。
- **[出站网络]** → DuckDuckGo 域名加入出站白名单，工具参数不接受任意 URL（SEC-10）。
- **[延迟增加]** → agent 多轮调用增加响应时间，受 `AGENT_MAX_TOOL_ITERATIONS` 与现有 LLM 总超时双重约束；工具调用耗时纳入日志（AI-10）。
- **[DuckDuckGo 限流]** → 免费服务可能限流，`DUCKDUCKGO_MAX_RESULTS` 默认 5 控制单次结果条数；限流时降级并标注，不重试轰炸。

## Migration Plan

1. 新增依赖 `mcp`、`duckduckgo-search`，更新 `requirements.txt` 与 Docker 构建。
2. 新增 `app/mcp/`（server 与工具）与 `app/services/agent/`（client、loop）。
3. 新增配置项到 `config.py` 与 `.env.example`（`DUCKDUCKGO_MAX_RESULTS`、`AGENT_MAX_TOOL_ITERATIONS`，无需搜索密钥）。
4. 改造 `qa.py` 接入 AgentLoop，保留 RAG 上下文。
5. 改造 `notification_parser.py` 接入 AgentLoop，时间解析逻辑不变。
6. 部署时无需配置搜索密钥；DuckDuckGo 不可达或限流时自动降级。
7. 回滚：移除新代码路径，恢复 `qa.py`/`notification_parser.py` 的原单次调用即可。

## Open Questions

- DuckDuckGo 搜索的 `max_results` 默认值与上限是否需要按能力（QA vs 通知解析）区分？当前设计统一默认 5、上限 10，可在实施时根据实际效果调整，不影响规范与架构。
