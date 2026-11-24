# 审核记录 02：脚本发现（含真实先红后绿证据）

本记录覆盖两处由自动化脚本发现、并经修复转绿的问题，构成课程第 ⑤ 节「门禁红→绿」证据。

---

## 发现 A：并发确认幂等失效（TOCTOU 竞态）

### 手段
新增并发用例 `backend/tests/test_concurrency_confirmation.py`：对同一通知并发 8 次确认，断言只产生一个批次（2 条待办）。用例采用文件 SQLite + NullPool，每请求独立连接/事务，建模生产并发。

### 查了什么
`ConfirmationService.confirm` 的幂等在并发下是否成立（`confirmation_key` 去重是否能挡住并发重放）。

### 判据
并发触发同一通知确认多次，`GET /api/v1/todos` 只返回一个批次（数量等于候选事项数），且所有请求返回 200。

### 结果（红→绿）
- **红（硬化前）**：首跑 `cd backend && python -m pytest tests/test_concurrency_confirmation.py -q --cov-fail-under=0` → `AssertionError: idempotency violated: expected 2 todos, got 16`，退出码 1。根因：check-then-create 无唯一约束、无行锁，8 个并发请求在任一提交前都查到空，全部插入（8×2=16）。
- **修复**：`confirmation_key` 改为逐事项唯一键 `notif:{nid}:user:{uid}:item:{i}` + 加唯一索引（模型 `unique=True`、迁移 `0017_*`）；`confirm` 将 create+commit 包进 `try/except IntegrityError`，捕获后 rollback 并按批次前缀重查返回胜方批次。详见 `reports/risk-concurrency.md` 与 `openspec/changes/course-submission-readiness/design.md` 决策 11。
- **绿（修复后）**：同一命令连续 2 次 → `1 passed`，退出码 0。
- **变异验证（TEST-08）**：临时把模型 `unique=True` 改为 `unique=False` → 用例红（`got 16`，退出 1）；恢复 → 绿（`1 passed`，退出 0）。证明用例能捕获回归。

### 复跑命令
```bash
cd backend && python -m pytest tests/test_concurrency_confirmation.py -q --cov-fail-under=0
```

---

## 发现 B：依赖存在已知漏洞

### 手段
`make check-security` 中的 `pip-audit -r requirements.txt` 扫描声明依赖（含传递闭包）。

### 查了什么
`backend/requirements.txt` 声明的依赖及其传递依赖是否存在已知漏洞。

### 判据
无可利用的已知漏洞；对无修复版本且评估不适用的，登记例外线后通过。

### 结果（红→绿）
- **红（升级前）**：`make check-security` → `Found 141 known vulnerabilities in 6 packages`，退出码 2。涉及 `Pillow 11.1.0`、`pypdf 5.1.0`、`python-multipart 0.0.20`、`python-jose 3.3.0`、`starlette 0.41.3`（fastapi 传递）、`ecdsa 0.19.2`。
- **修复**：升级直接依赖到已修复版本（`Pillow==13.0.0`、`pypdf==7.1.1`、`python-multipart==0.0.34`、`python-jose[cryptography]==3.5.0`、`fastapi==0.165.0`，后者带入修复版 starlette），并全量回归 `make check` 通过（141 passed，覆盖率 71.97%，apitest 46/46，前端 11/11），确认升级未破坏应用。
- **剩余 2 条**：`python-jose 3.5.0` PYSEC-2026-4298、`ecdsa 0.19.2` PYSEC-2026-1325，均**无修复版本**，经评估在本应用不适用（见 `reports/review-03.md`），在 `Makefile` 的 `PIP_AUDIT_IGNORE` 登记例外。
- **绿**：`make check-security` → `No known vulnerabilities found, 2 ignored` + `OK: no hardcoded secrets found`，退出码 0。

### 复跑命令
```bash
make check-security
```

## 关联
- `reports/risk-concurrency.md`、`reports/checklist.md`
- 变更归档：`docs/changes/course-submission-readiness/`
