# 八类规范技能化迁移

## 变更说明

- 原集中规范的八类正文迁移至八个项目技能的 references/standards.md，分别配有简短 SKILL.md。
- 原始文件 SHA-256：cb59b94f48a6b83867363f33d01e5fa431ee2433ee5b66550cbe39d4508d538b。
- 保留 98 条规则和检查判据，增加 PROD/BE/SEC/TEST/OPS/AI/DATA/REV 稳定编号。
- 新增短 AGENTS.md 约束加载，README 增加分类入口；后续按用户要求删除旧兼容索引并清理全部相关引用。
- 修正产品导语“README 尚未建立”的过时描述；原有规则行去除新增编号后逐行一致。
- 保留六个 OpenSpec 技能，不修改其内容、项目业务方案或配置。
- 八类均需独立入口和正文，本次迁移涉及 20 个文件；按用户授权的完整技能化范围作为同一迁移任务，评审可按“原文迁移”和“总纲接入”分别检查。

## 验证记录

适用规则：PROD-14（文档追溯）、TEST-12（文档适用检查）、REV-01/03/05/07（交付与证据）。

- 迁移前后 8 类、98 条，原规则行去除新编号后逐行一致。
- 八个 SKILL.md 使用 name/description frontmatter；参考文件非空且编号唯一。
- 执行 skill-creator 自带 quick_validate.py，具体命令与结果见执行结果。
- 校验总纲体积和新增 Markdown 引用；不声称新会话发现或业务运行验收已完成。
- 尚无统一业务门禁，纯文档迁移不新增无关业务测试。

## 评审结论

已完成本次范围内自检，未进行独立人工评审，也未形成合并或发布批准。
技能加载属于执行指导，不能证明模型始终遵守；业务约束须由测试、CI 与评审落实。
后续新会话须确认总纲和技能发现，本次仅验证目录与格式。

## 执行结果

每个新增技能分别校验（Python 需有 PyYAML，校验器为本机 skill-creator 工具）：

```powershell
python -X utf8 C:/Users/75567/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/teamproject-<领域>
```

```text
.agents/skills/teamproject-product: exit=0; Skill is valid!
.agents/skills/teamproject-backend: exit=0; Skill is valid!
.agents/skills/teamproject-security: exit=0; Skill is valid!
.agents/skills/teamproject-testing: exit=0; Skill is valid!
.agents/skills/teamproject-operations: exit=0; Skill is valid!
.agents/skills/teamproject-ai: exit=0; Skill is valid!
.agents/skills/teamproject-data: exit=0; Skill is valid!
.agents/skills/teamproject-review: exit=0; Skill is valid!
```

- AGENTS.md：4105 字节。
- 8 类 98 条原规则保留检查通过；编号唯一；新增 Markdown 引用全部有效。
- 本结果只覆盖技能迁移与格式，不代表业务测试、CI 或独立评审通过。
