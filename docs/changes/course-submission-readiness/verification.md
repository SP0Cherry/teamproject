# 验证记录：course-submission-readiness

## 环境
- OS：Windows（PowerShell）；`make` 不在 PATH，使用 Git for Windows 自带 `mingw32-make`。
- Python：3.11.7；后端虚拟环境 `backend\.venv`。
- 基线提交：`8671989`（`main`）；本变更未提交，证据生成于当前工作树。
- 注意：单文件跑 pytest 时需追加 `--cov-fail-under=0` 绕过全量覆盖率门禁；全量 `make check` 强制执行 ≥60%。

## 命令与结果

| 命令 | 退出码 | 结果 | 证据路径 |
| :--- | :--- | :--- | :--- |
| `make check`（或 `mingw32-make check`） | 0 | 后端 pytest `160 passed`，覆盖率 78.90%（≥60%，未调低阈值）；apitest 46/46；前端 11/11 | `reports/checklist.md`、`reports/risk-*.md` |
| `make check-security` | 0 | `pip-audit`：`No known vulnerabilities found, 2 ignored`；`check_secrets`：`OK: no hardcoded secrets found` | `reports/checklist.md` 第 6 类、`reports/review-03.md` 项 1 |
| `make bench` | 0 | 列表接口 P95=201.78ms ≤ 500ms，rps=105.7，all_200=True | `reports/bench.md` |
| `cd backend && python -m pytest tests/test_concurrency_confirmation.py -q --cov-fail-under=0`（硬化前） | 1 | `AssertionError: expected 2 todos, got 16`（红） | `reports/review-02.md` 发现 A、`reports/risk-concurrency.md` |
| 同上（硬化后，连续 2 次） | 0 | `1 passed`（绿） | 同上 |
| 变异：模型 `confirmation_key unique=False` 后重跑 | 1 | 复红（`got 16`）；恢复 `unique=True` → 绿 | `reports/risk-concurrency.md`（TEST-08） |
| `cd backend && python -m pytest tests/test_confirmation.py -q` | 0 | 事务幂等、空候选/缺 title 拒绝无部分批次 | `reports/risk-transaction.md` |
| `cd backend && python -m pytest tests/test_authz.py tests/test_confirmation.py::test_todo_owner_isolation -q` | 0 | 非成员 403、跨用户待办 404 | `reports/risk-authz.md` |
| `openspec validate --changes course-submission-readiness --strict` | 0 | 规约校验通过（1 passed, 0 failed，见任务 5.2） | 本变更目录 |

## 说明
- `pip-audit` 首次运行需联网拉取漏洞库；之后可离线复跑。2 条例外（`PYSEC-2026-4298`、`PYSEC-2026-1325`）均无修复版本且评估不适用，已在 `Makefile` `PIP_AUDIT_IGNORE` 登记，理由见 `reports/review-03.md` 项 1。
- 基准为进程内 ASGITransport（不含 TCP/uvicorn 调度开销），P95 为保守下界；并发测试在文件 SQLite（NullPool）上验证，caveat 见 `reports/risk-concurrency.md`。
- 所有「通过」均来自真实命令退出码，未伪造、未为过线放宽检查（REV-05）。

## 本次会话复跑（2026-11-24，基线同 `8671989`）

> 因机器中途关机，门禁回归任务被中断，本次重新复跑确认。代码与配置自上次成功跑通后未做任何修改（`backend/requirements.txt` 依赖版本、`Makefile` 的 `PIP_AUDIT_IGNORE` 均未变）。

| 命令 | 退出码 | 本次结果 | 备注 |
| :--- | :--- | :--- | :--- |
| `make check` | 0 | 后端 pytest `141 passed`、覆盖率 71.97%（≥60%）；apitest 46/46；前端 11/11 | 与上次一致，无回归 |
| `make bench` | 0 | P95=201.78ms ≤ 500ms，rps=105.7，all_200=True；`reports/bench.md` 已由脚本更新为本次结果（09:26） | 进程内基准数值随机器负载波动（上次 158.15ms），两次均远低于阈值 |
| `python scripts/check_secrets.py` | 0 | `OK: no hardcoded secrets found in tracked source files` | 离线快速，本次新鲜证据 |
| `make check-security`（`pip-audit` 部分） | **未拿到（用户决定停止）** | 纯 CPU 解析全量依赖树与漏洞匹配，块缓冲无中途输出；运行约 36 分钟（累计 CPU 2157s，近 100% 单核）仍未出结果，用户决定停止（已确认无残留进程） | 环境性能问题，非代码问题；`requirements.txt` 依赖版本与 `Makefile` 的 `PIP_AUDIT_IGNORE` 自上次成功跑通后未改动，上次会话结果为退出 0（`No known vulnerabilities found, 2 ignored`，见 `reports/review-02.md` L42-46）。建议在网络/机器空闲时手动复跑 `make check-security` 取一份新鲜退出码 |
