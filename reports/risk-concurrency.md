# 高风险三查：并发（concurrency）

## 风险
同一通知被并发确认多次时，可能因 check-then-create 竞态（TOCTOU）产生重复待办批次，破坏幂等。

## 手段
新增并发用例 `backend/tests/test_concurrency_confirmation.py`：注册用户 → 创建通知 → `asyncio.gather` 并发 8 次 `POST /api/v1/notifications/{id}/confirm`（相同候选事项）→ 断言 `GET /api/v1/todos` 只返回一个批次。用例采用文件 SQLite + NullPool，每请求独立连接/事务，建模生产并发。

## 查了什么
`ConfirmationService.confirm`（`backend/app/services/confirmation.py`）的幂等在并发下是否成立：`confirmation_key` 去重 + 唯一索引 + `IntegrityError` 回退是否能挡住并发重放。

## 判据
并发触发同一通知确认多次后：
1. 所有请求返回 200（race loser 不报错）；
2. 待办总数等于单次确认的候选事项数（只产生一个批次）。

## 结果
- **首跑（硬化前）红**：`expected 2 todos, got 16`，退出码 1（8 并发 × 2 事项 = 16）。
- **修复**：`confirmation_key` 改为逐事项唯一键 `notif:{nid}:user:{uid}:item:{i}`，加唯一索引（模型 `unique=True` + 迁移 `0017_todo_confirmation_key_unique.py`）；`confirm` 捕获 `IntegrityError` → rollback → 按批次前缀重查返回胜方批次（见 `design.md` 决策 11）。
- **修复后绿**：连续 2 次 `1 passed`，退出码 0。
- **变异（TEST-08）**：去掉唯一索引（`unique=False`）→ 红（`got 16`，退出 1）；恢复 → 绿。

## SQLite caveat
测试在文件 SQLite（NullPool，单库多连接）上验证。SQLite 写锁会串行化并发写，不能 100% 复刻 Postgres 多连接争用，但能端到端验证应用层去重 + 唯一索引回退逻辑，且命令可离线复跑。生产为 Postgres，唯一索引在多连接下同样强制。

## 复跑命令
```bash
cd backend && python -m pytest tests/test_concurrency_confirmation.py -q --cov-fail-under=0
```
（`--cov-fail-under=0` 仅在单文件跑时绕过全量覆盖率门禁；全量 `make check` 会强制执行 ≥60%。）
