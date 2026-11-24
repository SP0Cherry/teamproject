## 1. 依赖与配置

- [x] 1.1 在 `backend/requirements.txt` 新增 `mcp`（MCP 官方 SDK）与 `duckduckgo-search`，锁定版本并按 SEC-16 登记许可证；验证 `pip install -r requirements.txt` 成功且无许可证冲突
- [x] 1.2 在 `config.py` 新增 `duckduckgo_max_results`（默认 5）、`agent_max_tool_iterations`（默认 3）、`mcp_server_module` 配置项；验证 Settings 能从环境变量加载且未设置时使用默认值
- [x] 1.3 在 `.env.example` 补充上述键名（值留空），并在 README 说明用途；验证示例文件无真实密钥

## 2. MCP Server 与搜索工具

- [x] 2.1 新建 `backend/app/mcp/server.py`，使用 `mcp.server.mcpserver.MCPServer` 定义 server，注册 `duckduckgo_search` 工具（参数 `query: str`、`max_results: int = 5`）；验证 server 启动后 `list_tools` 返回该工具且 schema 正确
- [x] 2.2 实现 `duckduckgo_search` 工具逻辑：校验 query 非空且 ≤500 字符、`max_results` 在 1–10，调用 `ddgs` 客户端返回 `[{title, url, content}]`；验证参数非法时返回错误不发起外部请求
- [x] 2.3 实现 DuckDuckGo 不可达、超时或限流时的错误处理：工具返回搜索失败错误，不抛出未捕获异常；验证限流响应被正确识别并降级
- [x] 2.4 新建 `backend/app/mcp/__main__.py` 使 server 可通过 `python -m app.mcp` 以 stdio transport 运行；验证启动后 stdin/stdout 可进行 MCP JSON-RPC 通信

## 3. MCP Client 与 Agent 循环

- [x] 3.1 新建 `backend/app/services/agent/mcp_client.py`，实现 `MCPClient`：通过 `mcp.client.stdio.stdio_client` 连接 server 子进程，提供 `list_tools()` 与 `call_tool(name, args)`；验证能连接本地 server 并调用工具
- [x] 3.2 实现 server 子进程生命周期管理：应用启动时拉起，关闭时终止；server 异常退出时 client 标记不可用并降级；验证主进程退出后子进程被清理
- [x] 3.3 新建 `backend/app/services/agent/loop.py`，实现 `AgentLoop.run(system_prompt, user_content, capability)`：从 MCP client 获取工具列表并转为 LLM tools schema，循环调用模型，处理 `tool_calls` 并回注结果，最多 `agent_max_tool_iterations` 次；验证达到上限时返回最终结果
- [x] 3.4 AgentLoop 记录工具调用元数据（工具名、参数摘要、耗时、成功/失败），不记录搜索结果全文或用户问题；验证日志字段符合 AI-10
- [x] 3.5 工具调用失败或超时：AgentLoop 将错误标记回注模型并继续或返回降级结果，不抛出未捕获异常；验证工具抛错时主流程仍返回响应

## 4. 模型适配器扩展

- [x] 4.1 在 `model.py` 新增 `chat_completion_with_tools(messages, tools, ...)`：向 OpenAI 兼容接口发送 `tools` 字段，返回原始响应（含 `tool_calls`）；复用现有超时、重试、demo 模式与时间上下文注入逻辑
- [x] 4.2 demo 模式（无 LLM 配置）下 `chat_completion_with_tools` 返回不调用工具的确定性响应；验证未配置 LLM 时 QA 与通知解析仍可用且不请求工具

## 5. QA 集成

- [x] 5.1 改造 `QAService.ask()`：构建 RAG 上下文后调用 AgentLoop，system 提示包含本地资料片段与工具使用说明；验证模型可在需要时调用 `duckduckgo_search` 并将结果纳入回答
- [x] 5.2 回答区分来源：本地引用保持 `[doc:附件ID:片段序号]`，外部搜索结果标注标题与 URL；验证响应中两类来源格式可区分
- [x] 5.3 搜索工具网络故障或限流时 QA 降级为仅 RAG 回答，不伪造外部来源；验证 DuckDuckGo 不可达时回答不含外部来源且不报错

## 6. 通知解析集成

- [x] 6.1 改造 `notification_parser.py` 的 `extract_notification()`：接入 AgentLoop，保留 `EXTRACTION_PROMPT` 与时间上下文注入；验证时间字段仍由 `capture_time` + `normalize_candidate` 生成
- [x] 6.2 确保搜索结果不参与时间基准判定：时间字段生成路径不读取工具结果；验证构造含外部日期的搜索结果时，候选时间仍基于可信时间上下文
- [x] 6.3 搜索结果仅可补充标题、详情等非时间字段；验证搜索结果中的日期表述不改变 `due_at` 等时间字段

## 7. 安全与边界测试

- [x] 7.1 测试模型请求未登记工具：AgentLoop 拒绝调用，不发起外部请求；验证对应场景通过
- [x] 7.2 测试模型在工具参数中传入身份/权限字段：服务端忽略并使用真实身份；验证不泄露其他用户数据
- [x] 7.3 测试搜索结果含指令注入：结果仅作数据，系统指令不受影响；验证对应场景通过
- [x] 7.4 测试搜索参数非法（空 query、超长、超范围 max_results）：工具返回校验错误不发起请求；验证对应场景通过

## 8. 集成验证

- [x] 8.1 运行后端现有测试套件（`pytest backend/tests`），确保 QA 与通知解析原有测试通过，无回归
- [x] 8.2 端到端验证：QA 提问需外部知识的问题能触发 `duckduckgo_search` 并返回带 URL 的回答；通知解析能正常出候选且时间字段正确
- [x] 8.3 模拟 DuckDuckGo 不可达/限流时端到端验证：QA 与通知解析正常降级且不报错、不伪造搜索结果
- [x] 8.4 运行 `openspec validate agent-mcp-internet-search --type change --strict` 确认规范校验通过
