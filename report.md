# 课程项目报告：个人日常助手（teamproject）

## 头部

- **项目名称**：个人日常助手（teamproject）—— 通知解析与人工确认、待办、资料管理、AI 问答、日报与提醒，支持小组协作与组内资料/通知共享。
- **成员分工**：`<!-- TODO -->`（请填写各成员承担的模块与工作量，须能对上仓库提交记录与 `reports/` 证据）。
- **仓库地址**：https://github.com/SP0Cherry/teamproject
- **演示视频地址**：`<!-- TODO -->`（≤3 分钟，上传百度/北大网盘后填下载链接，见 `reports/review-03.md` 项 2）。
- **Harness / 使用模型**：端到端测试 harness 位于 `apitest/`（真实 ASGI + stub LLM + 真实 mcp-server 子进程，stub 模型标识 `apitest-stub-model`）。AI 生成代码所使用的具体模型名：`<!-- TODO -->`。
- **支撑目录**：`reports/`（课程证据）、`docs/changes/course-submission-readiness/`（变更归档）、`openspec/changes/course-submission-readiness/`（规约与任务）。
- **提交日期**：`<!-- TODO -->`。

---

## ① 一句话介绍（10 分）

个人日常助手：把自然语言描述的事务（如通知，含组通知）用 AI 解析成候选待办，经**人工确认**后落库，支持待办管理、资料共享、AI 问答与日报；成员可按小组选择是否把新组通知同步到自己的待办，全程有覆盖率与安全门禁兜底。

---

## ② AI 写了什么（20 分）

### AI 产出（≥3 项，均经 Harness/实跑验证）

1. **`scripts/check_secrets.py`** —— 扫描 git 跟踪文件中的私钥/令牌/密钥赋值，排除测试桩与文档，命中则退出 1。验证：`python scripts/check_secrets.py` → `OK: no hardcoded secrets found`，退出 0。
2. **`scripts/bench.py`** —— 列表接口性能基准（进程内 ASGITransport，隔离 SQLite，20 并发 × 200 请求）。验证：`make bench` → P95=201.78ms ≤ 500ms，rps=105.7，退出 0（见 `reports/bench.md`）。
3. **并发幂等硬化 + 测试** —— AI 在写并发用例时首跑即发现 TOCTOU 竞态（8 并发确认产生 16 条待办），随后给出修复：`confirmation_key` 改为逐事项唯一键 + 唯一索引（`backend/app/models/todo.py`、迁移 `backend/alembic/versions/0017_todo_confirmation_key_unique.py`）+ `ConfirmationService.confirm` 捕获 `IntegrityError` 回退（`backend/app/services/confirmation.py`）。验证：`backend/tests/test_concurrency_confirmation.py` 由红转绿；变异（去唯一索引）复红，恢复转绿（见 `reports/risk-concurrency.md`、`reports/review-02.md`）。
4. **统一门禁与 CI** —— `Makefile`（`check` / `check-security` / `bench`）与 `.github/workflows/ci.yml`，把测试、覆盖率、安全扫描纳入 push/PR 门禁（见 `reports/review-01.md`，闭合 SEC-17 / REV-05）。

### Harness

`apitest/`：`apitest/run_all.py` 拉起真实应用 ASGI + stub LLM + 真实 mcp-server 子进程，跑 46 项端到端用例并产出 `apitest/report.html`。AI 产出的代码改动均需通过 `make check`（pytest 160 项 + apitest 46 项 + 前端 11 项）方可视为完成。

### 七类核查清单

见 `reports/checklist.md`：接口入口 / 业务逻辑 / 数据库 / 公共函数（覆盖率门禁）/ 错误处理（故障注入）/ 安全（`make check-security`）/ 性能（bench，P95 ≤ 500ms）。

---

## ③ 审核记录（25 分）

共 3 份审核记录，存于 `reports/`，其中 2 份来自 AI/脚本，1 份为人工确认；每份均含**手段 / 查了什么 / 判据 / 结果**四件事与复跑命令。

| 记录 | 来源 | 核心内容 | 复跑命令 |
| :--- | :--- | :--- | :--- |
| `reports/review-01.md` | AI 自审 | 基于 `docs/changes/audit-and-fix-prototype-bugs/audit-summary.md`，核验本变更闭合 SEC-17（依赖扫描）与 REV-05（CI 门禁） | `make check-security` |
| `reports/review-02.md` | 脚本 | 并发幂等竞态与依赖漏洞两处「红→绿」证据（命令 + 退出码） | `cd backend && python -m pytest tests/test_concurrency_confirmation.py -q`、`make check-security` |
| `reports/review-03.md` | 人工确认 | 依赖扫描例外适用性、演示视频内容、GitHub 分支保护三项机器无法定判的确认 | `make check-security`（项 1） |

---

## ④ 高风险三查（25 分）

三项高风险各有一份记录，存于 `reports/`，含手段/查了什么/判据/结果与可复跑命令：

- **并发** `reports/risk-concurrency.md`：同一通知并发确认多次只产生一个批次（幂等）。命令：`cd backend && python -m pytest tests/test_concurrency_confirmation.py -q`。
- **事务** `reports/risk-transaction.md`：确认创建待办 + 标记通知在单事务内完成，校验失败无部分批次。命令：`cd backend && python -m pytest tests/test_confirmation.py -q`。
- **权限** `reports/risk-authz.md`：非成员看小组 403、跨用户操作待办 404，服务端按归属授权。命令：`cd backend && python -m pytest tests/test_authz.py tests/test_confirmation.py::test_todo_owner_isolation -q`。

---

## ⑤ 门禁与演示（20 分）

### 统一门禁

- `make check`：后端 pytest（含 `--cov-fail-under=60`）→ apitest → 前端测试。实跑：`160 passed`，覆盖率 78.90%（≥60%），apitest 46/46，前端 11/11，退出 0。
- `make check-security`：`pip-audit` + `scripts/check_secrets.py`。实跑：`No known vulnerabilities found, 2 ignored` + `no hardcoded secrets found`，退出 0（两条例外见 `reports/review-03.md` 项 1）。
- `make bench`：列表接口 P95=201.78ms ≤ 500ms，退出 0（`reports/bench.md`）。

### 红→绿证据

`reports/review-02.md` 记录两处由红转绿：并发幂等（`got 16` 退出 1 → 硬化后 `1 passed` 退出 0，含变异复红）与依赖漏洞（141 条退出 2 → 升级 + 例外登记后退出 0）。

CI 侧另有一次真实拦截：首次推送（`2ff364e`）`make check` 退出 2 被挡下，修复后（`3b4b2b2`）`make check` 与 `make check-security` 均退出 0。两次运行链接、根因与修复见 `reports/gate-blocked.md`。

### 演示视频

`<!-- TODO -->`：依次展示 `make check`、`make check-security` 全绿，再演示核心功能（通知解析 → 人工确认 → 待办），≤3 分钟，链接填入头部。

---

## ⑥ 复盘（不计分，必填）

1. **并发幂等的真实教训**：最初假设「既有 confirmation_key 幂等在并发下成立」，实跑并发用例即被证伪（产生 16 条）。说明幂等不能只靠应用层 check-then-create，必须有数据库唯一约束兜底，并在冲突时回退返回胜方结果。测试用「每请求独立连接」才真实建模并发，共享单 session 会掩盖竞态。
2. **依赖漏洞扫描的代价与边界**：`pip-audit` 首次跑出 141 条告警（多为补丁版本累积），升级直接依赖到修复版本后全量回归仍绿，说明升级可控；但剩余 2 条无修复版本，必须结合代码配置人工评估适用性并登记例外，不能为了绿灯而静默忽略或调低扫描等级。
3. **门禁纪律**：覆盖率阈值设为 60% 且未为过线调低（实测 78.90%）；所有「通过」都来自真实命令的退出码，不伪造检查结果。
4. **SQLite 与 Postgres 的差异留痕**：并发测试在 SQLite 上验证（可离线复跑），但已在 `reports/risk-concurrency.md` 明确 caveat，避免把单库行为误判为生产结论。
5. **后续可改进**：列表接口分页（BE-09）、限流（SEC-15）、提示词版本管理（AI-03/04）等仍在 `audit-summary.md` 后续变更清单中，未纳入本次交付范围。
