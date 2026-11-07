## Why

通知和资料分散在不同文件与渠道，用户需要反复查找任务要求、截止时间和来源。首期原型将通知确认、资料管理、小组协作和每日安排放进同一个可运行的工作台，验证从上传到执行的完整流程。

## What Changes

- 支持注册、登录、退出和个人数据隔离。
- 导入粘贴文本、PNG/JPG、PDF 和 DOCX 通知。AI 生成带来源的候选任务，用户核对和编辑后确认入待办，或向所选小组发布。
- 支持个人与组资料的上传、阅览、轻编辑、删除和知识库检索。长资料和长通知切片向量化，问答可追溯到已确认的待办或有权打开的资料位置。
- 支持创建和加入小组、成员共享资料及发布组通知。每位成员按组设置通知同步，默认关闭，开启后同步新发布的通知。
- 提供待办列表、月历、任务拆解建议和站内提醒。首页常驻每日任务、近期截止、逾期和有权访问的组内新增资料，AI 补充建议。
- 提供响应式中文工作台，重点打磨首页、通知确认、待办和小组详情。桌宠、动态壁纸和日常事件记录留待后续。

## Capabilities

### New Capabilities

- `account-access`：账号、会话与访问边界。
- `notification-intake`：导入、抽取、人工确认及组发布。
- `knowledge-library`：资料管理、版本化索引与撤权。
- `group-collaboration`：小组、共享和成员级通知同步。
- `task-planning`：待办列表、月历、拆解与提醒。
- `assistant-qa`：查询任务事实和带引用的资料问答。
- `daily-brief`：常驻日报和可降级的 AI 建议。
- `workspace-ui`：导航、页面状态、响应式和可达性。

### Modified Capabilities

## Impact

- 当前仓库已有项目规范和 OpenSpec 脚手架。本变更新增前端、API、后台处理、数据库迁移、部署及验证入口。
- 外部模型由服务端接入，使用隔离的配置、限额和测试替身。实现需要 OCR、文档解析和向量检索能力。
- [产品规范](../../../.agents/skills/teamproject-product/references/standards.md) PROD-01 至 PROD-13 约束首期行为。[评审规范](../../../.agents/skills/teamproject-review/references/standards.md) REV-01、REV-02、REV-07 约束分批交付和验收证据。
