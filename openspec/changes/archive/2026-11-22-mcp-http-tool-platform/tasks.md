## 0. 前置：归档基线与开放问题确认

- [x] 0.1 归档 `agent-mcp-internet-search`（`openspec archive`），确认主 spec 已含 `agent-tools` 及 `assistant-qa`/`notification-intake` 的工具调用 requirement；归档失败则停止并处理，验证：`openspec list --specs` 可见 `agent-tools`，主 spec 文本含「问答助手工具调用」与「MUST 不将 MCP 工具…用于时间基准」。
- [x] 0.2 确认 design 开放问题：①全局「教师/管理」角色是否需要显式 `role` 字段（默认按 owner 隔离等价实现，见决策 3）；②第 2 个工具选型（`formula_hint`/`unit_convert`/其他纯函数）；③流式协议采用 SSE。记录结论；若选全局角色，追加 `users.role` 迁移与角色中间件任务（会改变数据模型，需先更新 specs）。

## 1. 独立 mcp-server 工程（HTTP JSON-RPC + 鉴权 + ≥2 工具）

- [x] 1.1 新建根级 `mcp-server/` 工程骨架：`Dockerfile`（OPS-01 分阶段、不含机密）、`requirements.txt`（依赖登记 SEC-16）、`app/` 入口、配置从环境变量读取（BE-12）。验证：`docker build` 成功，镜像层无令牌。
- [x] 1.2 实现 `GET /health` 与 `POST /mcp` 单入口，处理 JSON-RPC 2.0 的 `initialize`/`tools/list`/`tools/call`，非法报文返回可读 JSON-RPC 错误不崩溃（对应 spec「HTTP MCP 工具服务协议与鉴权」）。验证：`curl /health` 200；畸形报文返回 error。
- [x] 1.3 实现 `MCP_AUTH_TOKEN` 鉴权：`tools/list`/`tools/call` 无令牌或错令牌返回 JSON-RPC error；令牌仅从环境变量读取，不写代码/镜像（SEC-08）。验证：无令牌被拒、正确令牌通过；grep 镜像与代码无令牌字面量。
- [x] 1.4 将 `duckduckgo_search` 工具迁移到 `mcp-server/`，保持名称/说明/输入结构与参数校验（AI-02、SEC-11）。验证：带令牌 `tools/list` 含该工具，`tools/call` 返回结构化文本。
- [x] 1.5 新增第 2 个工具（按任务 0.2 选型），写全名称/说明/输入结构，返回文本不含指令式语句（对应 spec「工具定义完整且返回数据」）。验证：`tools/list` 返回 ≥2 个工具且每项三项齐全。
- [x] 1.6 `docker-compose.yml` 新增 `mcp-server` 服务，与 `api` 同默认网络，健康检查指向 `/health`（OPS-03）；主应用通过 `MCP_TOOL_SERVER_BASE_URL` 连接。验证：`docker compose config` 含新服务，`pa_api` 能解析 `mcp-server` 主机名。

## 2. 数据模型与迁移（DATA-01/02/03/04）

- [x] 2.1 新增 alembic 迁移创建 `tool_servers` 表：`id, owner_id, name, base_url, token_cipher, has_token, status, discovered_tools(jsonb), last_error, created_at, updated_at`，`owner_id` 外键 + 索引（DATA-02）。验证：`alembic upgrade head` 成功，`downgrade` 可回滚。
- [x] 2.2 新增迁移创建 `skills` 表：`id, owner_id, name, capability, tool_refs(jsonb), version, created_at, updated_at`（DATA-01/02）。验证：迁移可逆。
- [x] 2.3 新增迁移创建 `tool_call_records` 表：`id, owner_id, tool_name, server_name, server_id(nullable), result, conversation_id, round_index, triggered_by, duration_ms, created_at`，只增不改（DATA-03）。验证：迁移可逆，无 update/delete 接口。
- [x] 2.4 新增 SQLAlchemy 模型与枚举（`server_status`、`tool_call_result`、`skill_capability`），命名符合 DATA-01。验证：模型导入无错，枚举值与课程「成功/被拒/出错」一致。
- [x] 2.5 更新 `docs/data-dictionary.md` 登记三张表的字段、类型、空值、归属、敏感等级（DATA-05/06）。验证：字典与迁移一致。

## 3. 宿主：工具服务器治理（SEC-01/02/08/14，BE-04/05）

- [x] 3.1 实现 `tool_servers` repository：CRUD 均带 `owner_id` 过滤，非所有者查询不返回行（SEC-02）。验证：单元测试用他人 owner_id 查询返回空。
- [x] 3.2 实现登记 service：令牌用环境变量密钥对称加密存 `token_cipher`，计算 `has_token`；忽略客户端传入的 `owner_id`/`token` 受控字段（SEC-11）。验证：登记后 DB 存密文，响应只含 `has_token`。
- [x] 3.3 实现连接 service：握手 `initialize` + 发现 `tools/list` 两步；任一步失败置 `status=error` 写 `last_error`、不更新清单；都成功置 `status=connected` 并**整体替换** `discovered_tools`（对应 spec「连接与发现」「重复连接不翻倍」）。验证：握手失败/发现失败均停在 error；成功后清单为最新。
- [x] 3.4 实现断开 service：置 `status=unconnected` 并清空 `discovered_tools`；删除 service 级联清理归属（DATA-02）。验证：断开后清单为空，调用不可发起。
- [x] 3.5 实现 REST 路由（BE-02 命名）：`/api/v1/tool-servers` CRUD + `/{id}/connect` + `/{id}/disconnect` + `/{id}/tools`；响应统一封装（BE-03），错误码合规（BE-04），非所有者返回 404 与不存在一致。验证：pytest 覆盖正常/失败/越权。
- [x] 3.6 验证令牌不回传：列表与详情响应全文 grep 不到令牌字符串，仅 `has_token` 为真（对应 spec「登记与令牌保密」）。

## 4. 宿主：技能配置与保存校验（BE-04/05，SEC-02/11）

- [x] 4.1 实现 `skills` repository：CRUD 带 `owner_id` 过滤（SEC-02）。验证：他人技能不可见。
- [x] 4.2 实现保存前三校验 service：①`tool_refs` 元素匹配 `^[a-z][a-z0-9_]*@[a-z][a-z0-9-]*$`；②服务器属于当前用户且 `status=connected`；③工具名在 `discovered_tools` 内；任一失败返回 `BUSINESS_*` 422 + 可读原因（对应 spec「技能工具引用与保存校验」）。验证：pytest 三条各触发拒绝 + 成功保存。
- [x] 4.3 实现 `/api/v1/skills` CRUD 路由（BE-02/03）。验证：接口可创建/查询/更新/删除，越权 404。

## 5. 宿主：调用记录持久化（DATA-03，SEC-02/14，BE-09）

- [x] 5.1 实现 `tool_call_records` repository：仅 insert 与分页 select（按 `owner_id` 过滤，默认 `page_size=20` 上限 100，BE-09），无 update/delete。验证：尝试更新/删除无接口。
- [x] 5.2 实现记录写入 service：每次调用写一条（tool@server、result、触发者、conversation_id、round_index、时间）；调用时若服务器已改名/删除解析不到归属则 `server_id=null` 且**不写记录**（对应 spec「服务器删除不写记录」）。验证：三状态各产生一条；删除服务器后调用不写记录。
- [x] 5.3 实现 `GET /api/v1/tool-call-records` 路由，默认条数上限，按 owner 隔离。验证：用户 A 查不到用户 B 的记录；他人记录标识访问返回与不存在一致（404）。
- [x] 5.4 验证记录不含敏感正文：记录字段无工具返回正文、无用户问题全文（SEC-14、AI-10）。

## 6. 重构 AgentLoop 与 HTTP client（AI-02/05/08，SEC-09/11）

- [x] 6.1 新增 HTTP MCP client：按 Base URL + 令牌调用 `tools/call`，失败抛可识别异常；移除 `mcp_client.py` 的 stdio 连接与 `backend/app/mcp/` 的 stdio server。验证：单测用替身服务器验证调用与失败（TEST-05）。
- [x] 6.2 重构 `AgentLoop` 入参：接收已解析的「工具引用 → 工具定义」映射，只把这些工具传给模型（最小权限，对应 spec「最小权限工具集」），不再全量 `list_tools`。验证：模型收到的 tools 仅含声明工具。
- [x] 6.3 实现宿主参数校验：模型 `tool_calls` 的参数按输入结构校验，通过才带令牌调用；越权（声明外工具）或校验失败记 `rejected`，不发请求（对应 spec「越权调用被拒」）。验证：越权调用不产生出站请求，状态为 rejected。
- [x] 6.4 实现结果检查器：命中指令式正则整条丢弃，超过 `TOOL_RESULT_MAX_CHARS` 截断；通过检查的结果作为 `tool` 消息回注用户侧，不拼入 system（AI-08、SEC-09）。验证：注入指令式结果被丢弃；超长被截断。
- [x] 6.5 实现双上限：`AGENT_MAX_TOOL_ITERATIONS`（轮次）+ `AGENT_MAX_TOTAL_TOOL_CALLS`（累计），任一到顶优雅降级用已有上下文作答（AI-05，对应 spec「循环上限与优雅降级」）。验证：调小上限后超限即停止并返回降级回答，不报错。

## 7. 流式改造（BE-03，对应 spec「流式调用事件与 meta」）

- [x] 7.1 `POST /api/v1/qa/ask` 改为 SSE（`text/event-stream`）：先推送 `meta` 事件（含 `tool_calls` 的 `{tool@server, status}`），再推送正文分片；流中错误可识别（BE-03/TEST-09）。验证：事件顺序 meta 先于正文。
- [x] 7.2 通知解析接口同样改 SSE + meta，时间字段生成逻辑不变（沿用 `capture_time`/`normalize_candidate`）。验证：流式输出时间结果与改造前一致。
- [x] 7.3 meta 中未连接或越权调用状态为 `rejected`，不显示成功（对应 spec「被拒状态可见」）。验证：用未连接服务器的技能提问，meta 显示 rejected。
- [x] 7.4 前端适配：QA 页面与通知页面消费 SSE，展示工具调用状态；无工具时主路径不阻断（对应 spec「连接失败不阻断主路径」）。验证：工具服务离线时 QA 仍返回本地资料回答。

## 8. OpenAPI 文档（BE-03/04）

- [x] 8.1 为新增路由补 Pydantic 模型的 `description`、`responses` 与错误码（登记/连接/工具/技能保存/记录查询），标明是否需登录。验证：`/openapi.json` 含新增路径与错误码。
- [x] 8.2 验证浏览器打开 `/docs` 可试调登记、连接、列出工具、断开、技能保存主要接口（对应 spec「接口文档」）。

## 9. apitest 端到端（TEST-01/03/06/08/09）

- [x] 9.1 新建根级 `apitest/` 目录与公共 HTTP 客户端封装（登录、Bearer 令牌、请求标识），独立测试命名空间（TEST-04）。验证：客户端可登录并调用受保护接口。
- [x] 9.2 编写用例：登记、连接、列出工具、断开、非所有者访问被拒（返回 404 与不存在一致）；按正常/失败/边界三类归组（TEST-03）。验证：运行用例全部通过。
- [x] 9.3 编写端到端用例：连接自建工具服务 → 保存引用了 `工具@服务器` 的技能 → 会话提问 → 调用记录中出现一条成功（对应课程「至少一条端到端」）。验证：断言返回内容与记录结果一致（TEST-08），不只看状态码（TEST-09）。
- [x] 9.4 实现 `run_all.py`：一键执行全部 apitest 并生成 HTML 报告（报告不入库，TEST-06）；任一失败非零退出（TEST-07）。验证：`python run_all.py` 生成报告，失败时退出码非零。
- [x] 9.5 验证三种结果在界面/记录中各可见一条：制造成功、被拒、出错各一次，记录查询均返回（对应 spec「调用记录持久化」）。

## 10. 回归、构建与验收证据

- [x] 10.1 后端 pytest 全量通过：新增用例 + 既有 `backend/tests/` 无回归（TEST-12）；断开外网替身测试仍通过（TEST-05）。验证：`pytest` 退出码 0。
- [x] 10.2 `docker compose up -d --build` 重建镜像，确认 `pa_api`/`pa_worker`/`pa_db`/`pa_web`/`mcp-server` 容器正常运行（依赖更新必须重建，避免旧镜像缺依赖——见项目记忆 lessons）。验证：`docker compose ps` 全 healthy。
- [x] 10.3 验收证据核查（课程第七部分）：①`/health` 正常 + 带令牌 `tools/list` 返回工具名 + `tools/call` 返回文本；②端到端连接→发现→绑定→触发→记录含 `tool@server`；③断开后用其工具的技能提问在保存或调用路径被拒；④调小上限后超限降级；⑤令牌未出现在前端/代码/镜像。逐项记录证据位置。
- [x] 10.4 同伴交叉验证准备（课程第七部分）：整理四项验证的请求/响应截图或日志片段占位说明（服务隔离、令牌不回传、断开即失效、记录只看自己范围），便于期末回溯。验证：四项各有可复现步骤。
- [x] 10.5 更新 `README.md`：新增 `mcp-server` 服务说明、`.env.example` 新增项、`apitest` 运行命令与报告位置（TEST-06）、不提交真实 `.env`。验证：README 命令可复现。
