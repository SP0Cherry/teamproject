# 项目总纲

本项目是 AI 通知与待办助手：通知解析经人工确认生成待办，小组共享资料与通知，并提供资料问答、日报和提醒。

## 规则加载与适用

本文件是项目常驻入口；八类正文位于仓库 `.agents/skills/`，由技能元数据发现，详细正文按任务加载。它们是项目约束，不因未被自动推荐而失效。

- 开始任务先按下表识别所有涉及领域，读取对应 `SKILL.md` 及其 `references/standards.md` 后再设计或修改。只加载相关领域，任务范围扩大时补读。
- 技能未自动显示时按表中路径直接读取；读取失败须说明受影响工作，不能假定已符合规范。
- 场景、页面与交互读产品；接口和后台逻辑读后端；身份、数据访问、上传与外部输入读安全；行为变更及缺陷修复读测试；数据模型、索引、缓存和留存读数据；模型、提示词、RAG 与评测读 AI；构建、环境和发布读运维；变更评审及交付判断读评审。
- 一个任务可适用多个技能。纯文案或格式变更按实际影响选择，不机械加载全部规则。
- 总纲负责共同底线与路由，技能负责流程，参考文件负责详细判据。用户明确要求和更高优先级指令优先；领域冲突须说明并解决，不静默选择或削弱约束。

## 始终适用的底线

1. 服务端按当前身份与资源关系授权，默认拒绝并隔离个人和小组数据。上传内容及模型输出不可信，不得改变系统规则或绕过人工确认。
2. 密钥不入库、不进前端与日志；日志及证据不包含无关个人信息或资料正文。
3. 确定性计算、授权和状态流转不交给模型；模型结果先校验，正式待办经人工确认。
4. 不伪造检查结果，区分已执行、失败、未执行和不适用。技能不替代测试、CI 或运行验收。
5. 不修改任务无关内容，复用已有 OpenSpec 工作流，不因技能调用扩大用户授权或执行外部发布。
6. 详细规则只在各技能参考文件维护；变更时同步入口及索引，稳定编号不重排。

## 分类入口

| 领域 | 技能名 | 入口 |
| :--- | :--- | :--- |
| 产品设计规范 | `teamproject-product` | [.agents/skills/teamproject-product/SKILL.md](.agents/skills/teamproject-product/SKILL.md) |
| 后端开发规范 | `teamproject-backend` | [.agents/skills/teamproject-backend/SKILL.md](.agents/skills/teamproject-backend/SKILL.md) |
| 安全开发规范 | `teamproject-security` | [.agents/skills/teamproject-security/SKILL.md](.agents/skills/teamproject-security/SKILL.md) |
| 测试规范 | `teamproject-testing` | [.agents/skills/teamproject-testing/SKILL.md](.agents/skills/teamproject-testing/SKILL.md) |
| 部署与运维规范 | `teamproject-operations` | [.agents/skills/teamproject-operations/SKILL.md](.agents/skills/teamproject-operations/SKILL.md) |
| AI 模型调用规范 | `teamproject-ai` | [.agents/skills/teamproject-ai/SKILL.md](.agents/skills/teamproject-ai/SKILL.md) |
| 数据规范 | `teamproject-data` | [.agents/skills/teamproject-data/SKILL.md](.agents/skills/teamproject-data/SKILL.md) |
| 评审与完成定义规范 | `teamproject-review` | [.agents/skills/teamproject-review/SKILL.md](.agents/skills/teamproject-review/SKILL.md) |

## 与规约和验证的关联

存在 OpenSpec 变更时，在提案、设计或任务的合适位置关联适用规则编号及参考路径；验证任务写明场景、检查方式和证据位置。没有提案时不编造已有任务或用例，按用户授权范围工作。

当前尚无统一业务门禁、业务测试或真实模型评测，不得声称它们已通过。后续建立后在 README 登记可重放命令；交付按评审技能记录适用检查和实际结果。纯文档不机械新增业务测试。

## 维护与发现

保持本文件简短，不复制八类正文。若发现列表或总纲未刷新，重新开启项目会话确认；可用 `$teamproject-backend` 等名称显式调用。
