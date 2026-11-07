## Why

原型系统已构建完成，但存在两类问题：一是尚未系统核查是否严格遵照 AGENTS.md 中八类规范（产品、后端、安全、测试、运维、AI、数据、评审），可能存在合规缺口；二是已发现两个影响体验的缺陷——侧边栏收起按钮仅播放动画但布局未实际收缩，以及 LLM 对复杂多事项文本的解析存在漏项。需要在一次变更中完成规范审计并修复缺陷，确保原型质量达标。

## What Changes

- 对全项目执行八类规范合规审计，逐项对照 [产品规范](../../../.agents/skills/teamproject-product/references/standards.md)、[后端规范](../../../.agents/skills/teamproject-backend/references/standards.md)、[安全规范](../../../.agents/skills/teamproject-security/references/standards.md)、[测试规范](../../../.agents/skills/teamproject-testing/references/standards.md)、[运维规范](../../../.agents/skills/teamproject-operations/references/standards.md)、[AI 规范](../../../.agents/skills/teamproject-ai/references/standards.md)、[数据规范](../../../.agents/skills/teamproject-data/references/standards.md)、[评审规范](../../../.agents/skills/teamproject-review/references/standards.md)，输出缺口清单并在本次变更内弥补可修复项。
- 修复侧边栏收起缺陷：点击收起按钮后，侧边栏应真正移出可视区域且主内容区同步扩展填充，而非仅播放位移动画。
- 提升 LLM 待办解析对复杂文本的召回率：优化提示词（补充多事项拆分与字段抽取的 few-shot 示例与约束）、增强输出校验（逐项校验 schema 中的 items）、对漏项场景增加重试或规则兜底，确保多事项文本不丢项。
- 关联 [AI 规范](../../../.agents/skills/teamproject-ai/references/standards.md) AI-04、AI-06、AI-09 与 [后端规范](../../../.agents/skills/teamproject-backend/references/standards.md) BE-03、BE-05。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `workspace-ui`：侧边栏收起交互要求——点击收起按钮后侧边栏实际移出可视区且主内容区 margin 同步归零，桌面端与移动端行为一致。
- `task-planning`：待办解析召回要求——对包含多个事项、嵌套时间地点或长文本的输入，LLM 解析须覆盖全部可识别事项，缺失字段以 null 表示而非丢弃整个事项；解析失败时回退规则解析并标注来源。

## Impact

- 前端：`frontend/src/layouts/WorkspaceLayout.vue` 的侧边栏 CSS 与交互逻辑。
- 后端：`backend/app/services/todo_parser.py` 的提示词、`_extract_json` 与逐项校验；`backend/app/services/model.py` 的 `validate_output` 深度校验 items。
- 测试：补充侧边栏交互测试与 LLM 解析多事项用例（含规则回退）。
- 审计产出：合规缺口清单及弥补记录，关联八类规范编号。
