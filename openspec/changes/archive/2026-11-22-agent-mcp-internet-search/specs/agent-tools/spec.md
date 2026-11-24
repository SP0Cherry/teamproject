## Purpose

为 agent 提供基于 MCP（Model Context Protocol）协议的工具调用运行时，支持工具登记、发现、调用与安全边界，首个工具为 DuckDuckGo 联网搜索（免费、无需 API Key），使助手能在本地数据之外获取外部信息。

## ADDED Requirements

### Requirement: MCP 工具运行时与 agent 循环

系统 SHALL 提供 MCP 协议运行时：服务端登记工具并通过 MCP server 暴露，agent 通过 MCP client 发现并调用工具。agent 循环由模型决定是否调用工具，调用结果回注模型上下文，最多迭代 `AGENT_MAX_TOOL_ITERATIONS` 次（默认 3），达到上限或模型不再请求工具时返回最终结果。工具调用失败或工具不可用时，循环降级返回已有结果并标记工具未执行，不抛出未捕获异常。

#### Scenario: 模型请求调用已登记工具

- **WHEN** 模型在响应中请求调用已登记的 `duckduckgo_search` 工具
- **THEN** agent 通过 MCP client 执行该工具，将结果回注模型，继续循环直至模型返回最终答案或达到迭代上限

#### Scenario: 模型请求未登记工具

- **WHEN** 模型请求调用未在服务端登记的工具
- **THEN** agent 拒绝调用，向模型返回工具不存在的提示，不发起任何外部请求，循环继续

#### Scenario: 达到迭代上限

- **WHEN** 模型连续请求工具调用达到 `AGENT_MAX_TOOL_ITERATIONS` 上限
- **THEN** agent 终止循环，基于已有上下文返回最终结果，不继续调用工具

#### Scenario: 工具调用失败降级

- **WHEN** 已登记工具调用返回错误或超时
- **THEN** agent 将错误信息标记后回注模型，循环可继续或返回降级结果，不影响主流程响应

### Requirement: DuckDuckGo 联网搜索工具

系统 SHALL 提供 `duckduckgo_search` 工具作为首个 MCP 工具，接收 `query`（必填，非空字符串，最长 500 字符）与 `max_results`（可选，1–10，默认 5）参数，调用 DuckDuckGo 搜索返回结构化结果列表，每项含 `title`、`url`、`content`（摘要）。该工具免费且无需 API Key，始终登记到 MCP server。搜索结果作为不可信外部内容，仅放入用户消息数据区，不拼入系统指令。

#### Scenario: 正常搜索

- **WHEN** agent 以合法 query 调用 `duckduckgo_search`
- **THEN** 返回至多 `max_results` 条结构化搜索结果，每条含标题、URL 与摘要

#### Scenario: 搜索不可达或被限流

- **WHEN** DuckDuckGo 网络不可达、超时或返回限流响应
- **THEN** 工具返回搜索失败错误，agent 标注「联网搜索暂不可用」并降级，不伪造搜索结果

#### Scenario: 搜索参数非法

- **WHEN** query 为空或超过 500 字符，或 `max_results` 超出 1–10 范围
- **THEN** 工具返回参数校验错误，不发起外部请求，错误信息回注模型

### Requirement: 工具安全边界

系统 MUST 仅允许调用服务端登记的工具，工具参数由服务端校验，模型参数不能覆盖调用者身份或资源授权范围。工具不得直接访问数据库、向量库或对象存储，不得修改正式待办或触发需人工确认的状态流转。联网搜索的出站目标仅限配置白名单内的 DuckDuckGo 域名，不接受模型或用户输入的任意 URL 作为请求目标。搜索结果中的指令不被执行，结果内容不改变系统规则。

#### Scenario: 模型尝试覆盖身份

- **WHEN** 模型在工具参数中传入用户标识或权限相关字段
- **THEN** 服务端忽略这些字段，使用当前请求的真实身份执行，返回结果不泄露其他用户数据

#### Scenario: 模型请求任意 URL

- **WHEN** 模型要求搜索工具访问非白名单 URL 或直接抓取指定链接
- **THEN** 工具拒绝请求，返回白名单错误，不发起出站连接

#### Scenario: 搜索结果包含指令注入

- **WHEN** 搜索结果摘要中包含要求忽略规则、读取密钥或执行操作的文本
- **THEN** 结果仅作为数据展示，系统指令不受影响，不执行其中任何指令

### Requirement: 工具调用可观测与降级

系统 SHALL 记录每次工具调用的工具名、参数摘要（不含敏感值）、耗时、成功/失败状态及调用来源（QA 或通知解析），不记录搜索结果全文或用户问题全文。工具不可用（网络故障、超时、限流）时，agent 继续返回不依赖该工具的结果，并在响应中标注工具未执行。

#### Scenario: 工具调用日志

- **WHEN** agent 调用任意工具
- **THEN** 日志记录工具名、参数摘要、耗时与结果状态，不含搜索结果正文或完整用户问题

#### Scenario: 搜索不可用时降级

- **WHEN** DuckDuckGo 不可达、超时或被限流
- **THEN** agent 返回不包含搜索结果的回答，并标注「联网搜索暂不可用」，不伪造搜索结果
