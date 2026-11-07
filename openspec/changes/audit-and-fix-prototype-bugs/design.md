## Context

原型系统已构建并部署。本次变更包含三部分：八类规范合规审计、侧边栏收起缺陷修复、LLM 待办解析召回率提升。动机与范围见 [proposal.md](proposal.md)。

当前代码观察：
- `frontend/src/layouts/WorkspaceLayout.vue` 中 `.main` 选择器出现两次（约第 171 行与第 230 行），第二次未声明 `transition`，存在覆盖风险；侧边栏使用 `position: fixed` + `transform: translateX(-100%)` 收起，主内容区通过 `margin-left` 让位。
- `backend/app/services/todo_parser.py` 的 `TODO_PROMPT` 仅含规则说明，无 few-shot 示例；`validate_output`（`model.py`）只校验顶层 `todos` 为数组，不逐项校验 items 的 `title` 必填与字段类型；LLM 失败时抛错而非回退规则解析。
- 八类规范标准位于 `.agents/skills/teamproject-*/references/standards.md`，尚无系统性合规核查记录。

## Goals / Non-Goals

**Goals:**
- 输出八类规范逐项合规审计结果，弥补本次变更范围内可修复的缺口。
- 侧边栏收起/展开在桌面端与移动端均实际改变布局，动画与状态一致。
- LLM 解析多事项文本不丢项，畸形输出回退规则解析，解析来源可识别。

**Non-Goals:**
- 不重构后端分层或数据模型（审计发现的架构性缺口另立变更）。
- 不引入新的外部依赖或向量检索策略。
- 不修改通知解析（`notification_parser.py`），仅针对待办解析（`todo_parser.py`）。
- 不处理桌宠、动态壁纸等未实现功能的合规性。

## Decisions

### 1. 侧边栏修复：清理重复 CSS 并校验状态绑定

**决策**：删除 `WorkspaceLayout.vue` 中重复的 `.main` 规则，保留含 `transition: margin-left 0.2s` 的定义；确认 `:class="{ 'sidebar-collapsed': !sidebarOpen }"` 与 `@media (min-width: 768px) .main:not(.sidebar-collapsed) { margin-left: 240px }` 的配合；桌面端收起时主内容区 `margin-left` 归零，移动端收起时侧边栏 `translateX(-100%)` 并隐藏遮罩。

**理由**：重复的 `.main` 规则可能导致 `transition` 或 `margin-left` 被后续同特异性规则覆盖，使动画播放但布局不变。单一规则源可消除歧义。

**替代方案**：用 `width` 代替 `margin-left` 控制主内容区宽度——但 `position: fixed` 的侧边栏不占流内空间，`margin-left` 是更直接的让位方式。

### 2. LLM 解析：提示词增强 + 深度校验 + 失败回退

**决策**：
- **提示词**：在 `TODO_PROMPT` 中补充 2-3 个 few-shot 示例，覆盖多事项拆分、中文时间、地点抽取、字段缺失填 null；明确要求"每个可识别事项必须输出，不得合并或省略"。
- **深度校验**：扩展 `validate_output` 支持 `items` schema 校验，逐项检查 `title` 必填且为字符串，其余字段为字符串或 null；不合规项剔除但不中断整体解析。
- **失败回退**：`parse_todos` 中 LLM 调用抛出 `ModelError` 或 JSON 解析失败时，不直接抛错，而是调用 `_demo_parse` 规则解析并标记 `parser: "rule"`；仅当规则解析也失败时返回业务错误。
- **漏项兜底**：若 LLM 返回的 `todos` 数组长度为 0 但输入文本明显包含多个事项（按分隔符切分后片段数 > 1），自动回退规则解析。

**理由**：AI-06 要求结构化结果按 schema 校验；AI-05 要求依赖故障降级而非失败。few-shot 示例是提升复杂文本召回率的最低成本手段。

**替代方案**：使用 function calling / structured output API——但当前 `response_format` 已使用 `json_object`，部分供应商不支持严格 schema，深度校验更通用。

### 3. 合规审计：逐项对照并记录缺口

**决策**：按八类规范的每条标准（如 BE-01 至 BE-16、AI-01 至 AI-10 等）逐项检查代码与配置，输出审计清单，标注"符合/不符合/不适用"及证据位置。对不符合项中可在本次修复的（如错误码、日志脱敏、参数校验）一并修复；架构性缺口（如事务内外部调用、Outbox 模式）记录为后续变更。

**理由**：AGENTS.md 要求变更关联适用规则编号；评审规范要求记录检查与实际结果。

**替代方案**：仅审计与本次 bug 相关的规范——但用户明确要求"彻查项目，是否严格遵照八类规范"，需全量审计。

## Risks / Trade-offs

- **[提示词变更影响解析结果]** → 变更后用既有测试用例回归，确保简单文本解析不退化；记录提示词版本。
- **[规则回退在演示模式下始终触发]** → `has_llm` 判断保持不变，仅在 LLM 配置存在但调用失败时回退；演示模式直接走规则。
- **[审计发现大量缺口]** → 按"本次可修复"与"后续变更"分类，不扩大本次变更范围；后续缺口登记到 `docs/` 或新 OpenSpec 变更。
- **[CSS 清理引入回归]** → 桌面端（≥768px）和移动端（<768px）分别手动验证收起/展开/导航点击行为。
