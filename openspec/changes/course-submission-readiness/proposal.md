## Why

课程第 11 课「展示与复盘」以可复核的交付物为评分依据：`report.md` 六节 + `reports/` 下的评审记录（≥3 份）、高风险三查（并发/事务/权限各一份）、压测报告，以及统一门禁（`make check` 挂进 CI 并受 `main` 分支保护）、七类核查清单、演示录屏。第 2/3/4/5 节合计 90 分全部依赖这些可查、可复跑的证据。

当前仓库经审计存在系统性缺口：根目录无 `report.md`、无 `reports/` 目录、无 `Makefile`、无 `.github/workflows/`、无七类核查清单、无并发幂等测试、无压测报告、无覆盖率门禁；`README.md` 也自承「尚无覆盖安全扫描和全部浏览器流程的统一业务门禁」。不补齐则 90 分无法拿满，且「未经审核直接合入 AI 原生代码」的红线（课件）会因无评审记录对应而暴露风险。本变更一次性建立门禁、证据与报告的可验证契约，不改运行时业务行为。

## What Changes

- 新增根级 `Makefile`：`make check` 编排后端 pytest（含覆盖率阈值）、`apitest/run_all.py`、前端 `npm test`，任一失败以非零退出码阻断；`make check-security` 编排依赖审计与密钥扫描，高危 >0 即红（REV-05、TEST-06、TEST-07）。
- 新增 `.github/workflows/ci.yml`：PR 与 push 到 `main` 时运行 `make check` 与 `make check-security`，作为门禁的 CI 一环。
- 新增 `reports/` 交付目录：
  - `checklist.md`：七类核查清单（接口入口/业务逻辑/数据库/公共函数/错误处理/安全/性能），每类写清核查问题、检查手段与对应命令/路径。
  - `review-01.md`～`review-03.md`：≥3 份评审记录，每条写全「手段/查了什么/判据/结果」，其中 ≥2 份标注由 AI 自审或脚本发现；从既有 `docs/changes/audit-and-fix-prototype-bugs/` 审计材料提炼，不编造。
  - `risk-concurrency.md` / `risk-transaction.md` / `risk-authz.md`：高风险三查，每条四件事齐全且命令可复跑。
  - `bench.md`：压测报告，含脚本参数、P95/吞吐与阈值对照（列表接口 p95 ≤500ms，OPS-09）。
- 新增后端并发幂等测试：`asyncio.gather` 并发确认同一通知多次，断言只生成一条待办（TEST-01、TEST-04：真实测试库、独立连接），作为 `risk-concurrency.md` 的复跑命令来源。
- 新增轻量压测脚本，产出 `reports/bench.md`；固定环境与数据规模，断网可重放（TEST-05）。
- 新增覆盖率门禁：`backend/requirements-dev.txt` 加 `pytest-cov`，`backend/pytest.ini` 配置 `--cov` 与 `--cov-fail-under` 阈值。
- 新增根级 `report.md`：头部（项目/分工/仓库地址/视频地址/Harness/支撑目录/提交日期）+ 六节，一到两页，每节文件写全路径、命令可直接复制。
- `README.md` 登记统一门禁命令、退出码与证据位置（REV-05、TEST-06）。
- `docs/changes/course-submission-readiness/` 归档本变更证据（REV-07）。
- 需人工完成（无法由本变更自动落地）：录制 ≤3 分钟演示录屏并上传网盘、在 GitHub 仓库开启 `main` 分支保护要求 CI 通过。

## Capabilities

### New Capabilities

- `delivery-gate`: 仓库级交付质量契约——统一门禁命令（`make check` / `make check-security`）的退出码语义、CI 与主干分支保护的合入门禁、评审/三查/压测证据在 `reports/` 的归档与可复核性、七类核查清单的齐备性、以及课程交付报告 `report.md` 的结构与可查性。均为可由命令或文件存在性验证的交付行为，不涉及运行时业务接口。

### Modified Capabilities

无。并发幂等测试仅验证 `notification-intake` / `task-planning` 既有的确认幂等行为，不改变其规约要求；其余均为工程化与文档补齐，无 spec 级业务行为变化。

## Impact

- **代码**：`backend/tests/` 新增并发确认幂等用例；新增轻量压测脚本（置于 `scripts/` 或 `backend/tests/`，在 design 中定）。
- **配置**：根级 `Makefile`、`.github/workflows/ci.yml`、`backend/pytest.ini`（追加 cov 配置）、`backend/requirements-dev.txt`（追加 `pytest-cov` 与安全扫描工具）。
- **文档**：根级 `report.md`、`reports/` 下 7 份证据文件、`README.md` 门禁登记、`docs/changes/course-submission-readiness/` 变更归档。
- **依赖**：新增 `pytest-cov`；安全扫描优先选免密钥方案（`pip-audit` 做依赖审计，密钥扫描在 design 中评估 `gitleaks` 或纯脚本 grep，避免引入需配置的服务）。
- **运维**：CI 在 PR/push 时运行门禁；`main` 分支保护由人工在 GitHub 设置开启。
- **规模约束（REV-02）**：本变更手工维护文件数接近 15 件上限，超出部分由课程 rubric 强制要求「一份记录一个文件」所致，非无关扩张；按 REV-06 登记例外，且每份证据文件保持精简。
- **不影响**：运行时业务行为、接口契约、数据模型与迁移；不引入新的外部运行时依赖。
