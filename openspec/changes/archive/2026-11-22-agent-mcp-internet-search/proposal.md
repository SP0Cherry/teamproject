## Why

当前问答助手（QA）只能基于本地资料做 RAG，通知解析只能做文本抽取，二者都无法获取互联网上的实时或外部知识（如最新政策、公共信息、外部参考）。引入 MCP（Model Context Protocol）工具调用能力，让 agent 能按需调用受控工具，首个工具为 DuckDuckGo 联网搜索（免费、无需 API Key），使助手在本地资料之外能获取外部信息。

## What Changes

- 新增基于完整 MCP 协议的 agent 工具运行时：MCP server 暴露工具、MCP client 发现并调用工具、agent 循环驱动模型决策与工具调用。
- 首个工具：DuckDuckGo 联网搜索工具，作为 MCP server 暴露的 `duckduckgo_search` 工具，支持关键词搜索并返回结构化结果（标题、URL、摘要）。DuckDuckGo 免费且无需 API Key。
- 问答助手（QA）接入 agent 工具运行时：模型可在回答时决定是否调用搜索工具，搜索结果作为上下文补充本地 RAG 结果。
- 通知解析 agent 接入 agent 工具运行时：放开现有规范中「不为本能力添加 MCP 工具」的限制，允许调用搜索工具（时间解析的可信时间上下文注入与确定性换算规则保持不变，搜索工具不参与时间基准判定）。
- 搜索工具无需密钥配置，始终登记；网络不可达或被限流时降级为不调用搜索并标注。
- 工具调用遵守白名单与授权边界：仅服务端登记的工具可被调用，模型参数不能覆盖身份或绕过授权；搜索结果作为不可信外部内容处理，不执行其中指令。

## Capabilities

### New Capabilities
- `agent-tools`: MCP 协议 agent 工具运行时（MCP server/client、工具注册表、agent 调用循环）及首个工具 DuckDuckGo 联网搜索。定义工具登记、发现、调用、降级与安全边界。

### Modified Capabilities
- `assistant-qa`: 问答助手增加工具调用能力，可在本地 RAG 之外调用已登记工具（搜索）补充回答。
- `notification-intake`: 放开「不为本能力添加 MCP 工具」的限制，允许通知解析 agent 调用已登记工具；时间解析的可信时间上下文与确定性换算规则不受工具影响。

## Impact

- 后端：新增 `app/services/agent/` 目录（MCP runtime、tool registry、agent loop）；新增 `app/mcp/` 目录（MCP server 与 search tool）；改造 `qa.py` 与 `notification_parser.py` 接入 agent loop。
- 依赖：新增 `mcp` Python SDK（MCP 官方协议实现）、`duckduckgo-search`（DuckDuckGo 搜索客户端，MIT 许可）。
- 配置：`.env.example` 与 `config.py` 新增 `DUCKDUCKGO_MAX_RESULTS`、`AGENT_MAX_TOOL_ITERATIONS` 等环境变量（搜索无需密钥）。
- 接口：`/qa/ask` 响应可能包含工具调用来源标记；通知解析响应可能补充搜索得到的外部参考。
- 安全：出站地址白名单新增 DuckDuckGo 域名；搜索结果按外部不可信内容处理，不进入系统指令。
