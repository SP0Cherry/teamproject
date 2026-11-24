# 变更说明：course-submission-readiness（交付门禁 + 课程证据）

## 场景与目标
本变更为课程「互联网软件开发」第 11 课展示与复盘交付而做，闭合已批准规约 `openspec/changes/course-submission-readiness/` 中能力 `delivery-gate`：建立统一质量门禁（测试 + 覆盖率 + 安全扫描 + 基准），并在仓库根提供 `report.md` 与 `reports/` 课程证据，使 AI 生成代码可审计、门禁可重放、风险可追溯。

## 基线与提交
- 基线提交：`8671989`（`main`）。
- 本变更在该基线之上的工作树完成，**尚未提交**；提交号待提交后补入。验证证据均生成于该工作树状态。

## 范围（手工维护文件，共 22 个，触发 REV-02 例外 → 见 `exception-rev02.md`）
门禁与 CI：
- `Makefile`（新增 `check` / `check-security` / `bench` 目标）
- `.github/workflows/ci.yml`（push/PR 到 `main` 跑门禁）
- `backend/requirements-dev.txt`、`backend/pytest.ini`（覆盖率门禁 ≥60%）

并发幂等硬化（apply 阶段发现，已更新 `design.md` 决策 11）：
- `backend/app/models/todo.py`（`confirmation_key` 改唯一）
- `backend/app/repositories/todo.py`（新增按批次前缀查询）
- `backend/app/services/confirmation.py`（`IntegrityError` 回退）
- `backend/alembic/versions/0017_todo_confirmation_key_unique.py`（唯一索引迁移）
- `backend/tests/test_concurrency_confirmation.py`（并发幂等用例）

依赖漏洞修复：
- `backend/requirements.txt`（fastapi/starlette/pypdf/Pillow/python-jose/python-multipart 升级）

课程证据与交付：
- `reports/`（bench、checklist、review-01/02/03、risk-concurrency/transaction/authz，共 8 份）
- `report.md`（根级课程报告）
- `README.md`（登记统一门禁）
- `openspec/changes/course-submission-readiness/design.md`、`tasks.md`（规约/任务更新）

## 关键决策（apply 阶段偏离已批准设计）
**决策 11（新增）**：并发幂等竞态。首次并发用例即红（8 并发确认同一通知产生 16 条待办），证明原有 check-then-create 幂等在并发下失效。规约强制「只产生一份结果」为绿，因此必须修复而非降级。选择：逐事项唯一键 `notif:{nid}:user:{uid}:item:{i}` + 唯一索引 + `IntegrityError` 捕获后 rollback 重查返回胜方批次。拒绝的替代：单独批表（改动过大）、`SELECT FOR UPDATE`（SQLite 忽略，且引入锁竞争）。详见 `openspec/changes/course-submission-readiness/design.md` 决策 11 与 `reports/risk-concurrency.md`。

## REV-08 复盘留痕（失败 / 返工）
1. **并发首跑红**（`got 16`，退出 1）→ 硬化后绿（`1 passed`，退出 0）。教训：幂等必须数据库唯一约束兜底；测试需每请求独立连接。
2. **`pip-audit` 首跑红**（141 条告警，退出 2）→ 升级可修复依赖 + 对 2 条无修复且评估不适用的登记例外 → 绿。教训：`pip-audit -r requirements.txt` 扫的是声明 pin 而非已装版本，必须同步更新 requirements.txt；例外须有理由并登记，不得为过线调低扫描等级。

## 关联证据
- 课程证据目录：`reports/`
- 验证记录：`verification.md`
- 评审结论：`review.md`
- 例外登记：`exception-rev02.md`
- 上游审计（识别 SEC-17 / REV-05 缺口）：`docs/changes/audit-and-fix-prototype-bugs/audit-summary.md`
