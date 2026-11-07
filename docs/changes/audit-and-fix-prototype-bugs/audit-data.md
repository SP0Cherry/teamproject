# 数据规范合规审计

审计范围：DATA-01 至 DATA-09
审计日期：2026-11-07

## 审计结果

| 规范项 | 判定 | 证据 |
| :--- | :--- | :--- |
| DATA-01 命名与类型 | 符合 | 表名小写复数、字段 snake_case；`due_at` 使用 DateTime(timezone=True) |
| DATA-02 主键与外键 | 符合 | UUID 主键；外键带 ForeignKey 约束；Todo 有 owner_id、group_id |
| DATA-03 审计字段 | 符合 | `TimestampMixin` 提供 created_at、updated_at |
| DATA-04 迁移纪律 | 符合 | alembic 迁移版本化（0001-0014）；只增不改 |
| DATA-05 数据字典 | 不符合 | `docs/data-dictionary.md` 存在但需核查是否完整覆盖所有表 |
| DATA-06 敏感数据分级 | 部分符合 | 密码哈希存储；需核查分级规则与脱敏实现 |
| DATA-07 留存与删除 | 不符合 | 无留存清单与保留期定义 |
| DATA-08 跨存储一致性 | 部分符合 | 向量切片有版本；需核查删除时的跨存储清理 |
| DATA-09 测试数据 | 符合 | 测试使用合成数据 |

## 缺口清单

1. **DATA-07**：缺少留存与删除清单 —— 后续变更
2. **DATA-05**：需核查数据字典完整性 —— 本次修复（核查 docs/data-dictionary.md）
3. **DATA-08**：需核查删除时向量/缓存清理 —— 后续变更
