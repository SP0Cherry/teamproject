## 1. 门禁基础设施

- [x] 1.1 新建 `scripts/check_secrets.py`：扫描 git 跟踪文件中的硬编码密钥特征（JWT_SECRET 非空默认值、私钥、token 字面量），排除 `.env`（已 gitignore）与测试替身，命中则非零退出；验证：`python scripts/check_secrets.py` 在干净仓库上退出 0
- [x] 1.2 新建 `scripts/bench.py`：起绑定 127.0.0.1 的真实 uvicorn（隔离 SQLite + stub LLM，不连业务库/真实模型），建合成数据，并发压 `GET /api/v1/todos`，统计 P95/吞吐并断言 P95 ≤ 500ms，写入 `reports/bench.md`；验证：`python scripts/bench.py` 生成 `reports/bench.md` 且含 P95 与阈值对照
- [x] 1.3 新建根级 `Makefile`，提供 `check` / `check-security` / `bench` 目标，recipe 用 `cd <dir> && <cmd>` 单行写法兼容 cmd/bash，任一子命令非零则整体非零；验证：`mingw32-make -n check` 与 `mingw32-make -n check-security` 打印命令序列无语法错误
- [x] 1.4 `backend/requirements-dev.txt` 追加 `pytest-cov` 与 `pip-audit`；`backend/pytest.ini` 追加 `addopts = --cov=app --cov-report=term-missing --cov-fail-under=<阈值>`（起步 60，按实测微调且不删测试过线）；验证：安装后 `cd backend && python -m pytest --version` 显示 pytest-cov 生效
- [x] 1.5 新建 `.github/workflows/ci.yml`（ubuntu-latest），on: push 到 main + pull_request，步骤含 checkout、setup-python 3.11、setup-node、安装依赖、`make check`、`make check-security`，任一步失败即 workflow 失败；验证：YAML 语法校验通过，触发条件与步骤齐全

## 2. 并发幂等硬化与测试

> apply 发现：首跑并发用例红（8 并发确认 → 16 条，TOCTOU），违反 spec「只产生一份结果」。先硬化至绿灯，再保留用例与变异验证。修复不改变接口契约，见 design.md 决策 11。

- [x] 2.0a `backend/app/models/todo.py`：`confirmation_key` 加 `unique=True`（逐事项唯一键，列仍可空，NULL 不冲突）；验证：模型字段声明含 unique
- [x] 2.0b 新增迁移 `backend/alembic/versions/0017_todo_confirmation_key_unique.py`：把既有 `ix_todos_confirmation_key` 非唯一索引转为唯一索引，downgrade 可逆；验证：`alembic heads`/`history` 识别为 head 且链式正确，文件 py_compile 通过（全链 upgrade 需 PG，test_migrations 不在 make check 内）
- [x] 2.0c `backend/app/services/confirmation.py` + `repositories/todo.py`：`confirmation_key` 含 item index；repo 新增 `list_by_confirmation_batch`（按批次前缀 like 查）；`confirm` 把 create+commit 包 `try/except IntegrityError` → rollback → 重查返回胜方批次；验证：全量后端 pytest 140 passed，`test_confirmation.py` 串行幂等用例仍全绿
- [x] 2.1 完善 `backend/tests/test_concurrency_confirmation.py`：用「每请求独立连接」（文件 SQLite + NullPool）建模生产并发事务，`asyncio.gather` 并发对同一通知触发多次确认，断言只生成一条批次；验证：连续 2 次 `cd backend && python -m pytest tests/test_concurrency_confirmation.py -q --cov-fail-under=0` 退出 0 且 1 passed
- [x] 2.2 轻量变异验证（TEST-08）：移除唯一索引（`unique=False`）后用例红（`got 16`，exit 1），恢复后转绿（`1 passed`，exit 0）；另保留硬化前首跑红（`got 16`）作为真实红→绿证据；验证：无 MUTATION 标记残留，恢复后用例绿灯

## 3. 实跑门禁并产出 reports/ 证据

- [x] 3.1 实跑 `make check` 与 `make check-security`，捕获真实退出码与输出；覆盖率首跑 71.97% ≥ 60% 无需补测试；升级漏洞依赖后两门禁均退出 0；验证：退出码与 `reports/` 记录一致，无失败被掩盖
- [x] 3.2 实跑 `make bench`，生成/更新 `reports/bench.md`，含固定环境、数据规模、脚本参数、P95、吞吐及与 500ms 阈值的对照结论；验证：`reports/bench.md` 存在且结论明确（P95=158.15ms ≤ 500ms 通过），命令可断网重放
- [x] 3.3 写 `reports/checklist.md`：列出七类（接口入口/业务逻辑/数据库/公共函数/错误处理/安全/性能），每类写清核查问题、检查手段与对应命令/路径，指向真实存在的检查；验证：打开可数出七类，抽查命令可跑、路径存在
- [x] 3.4 写 `reports/review-01.md`（AI 自审发现，基于 `docs/changes/audit-and-fix-prototype-bugs/` 真实材料）：写全手段/查了什么/判据/结果四件事并给复跑命令；验证：四件事齐全，引用命令可复跑
- [x] 3.5 写 `reports/review-02.md`（脚本发现，含真实先红后绿证据）：四件事齐全并给复跑命令；验证：含红→绿证据（命令+退出码），引用命令可复跑
- [x] 3.6 写 `reports/review-03.md`（人工确认，仅确认机器给不出判据的项）：四件事齐全，确认结论写成规则或记录落点；验证：四件事齐全，结论有对应落点
- [x] 3.7 写 `reports/risk-concurrency.md`：四件事齐全，复跑命令指向 2.1 的测试，并记录 SQLite caveat；验证：`cd backend && python -m pytest tests/test_concurrency_confirmation.py -q` 可复跑且结果与记录一致
- [x] 3.8 写 `reports/risk-transaction.md`：基于 `backend/tests/test_confirmation.py` 的事务幂等测试，四件事齐全并给复跑命令；验证：引用的 pytest 命令可复跑
- [x] 3.9 写 `reports/risk-authz.md`：基于 `backend/tests/test_authz.py` 的跨范围越权 404 测试，四件事齐全并给复跑命令；验证：引用的 pytest 命令可复跑

## 4. 交付报告与文档登记

- [x] 4.1 写根级 `report.md`：头部（项目/分工/仓库地址 `https://github.com/SP0Cherry/teamproject`/演示视频地址/Harness/支撑目录/提交日期）+ 六节，已知项填实，用户专有字段留 `<!-- TODO -->` 占位，每节引用写全路径；验证：含头部七项与六节，引用路径均存在
- [x] 4.2 更新 `README.md`：登记统一门禁命令 `make check` / `make check-security`、退出码语义、证据位置（`reports/`），注明 Windows 用 `mingw32-make`、pip-audit 首次需联网（REV-05、TEST-06）；验证：README 可查到一条完整测试/门禁命令与报告位置
- [x] 4.3 新建 `docs/changes/course-submission-readiness/`：含变更说明、验证记录、评审结论三类材料（REV-07），并登记 REV-02 例外（文件数超 15 的范围/理由/风险/替代控制/责任人/批准人/到期日，REV-06），与 `reports/` 互相链接；验证：目录含三类材料与例外登记，双向链接可打开

## 5. 验收与人工收尾

- [ ] 5.1 全量回归：`make check` 全绿、`make check-security` 退出 0、`make bench` 通过；验证：三者退出码均为 0。本次（2026-11-24）复跑：`make check` 退出 0（后端 pytest 最新 `160 passed` / cov 78.90%，补 P0 覆盖用例后仍 ≥60% 门禁；apitest 46/46、前端 11/11 维持此前全绿）、`make bench` 退出 0（P95 201.78ms）、`python scripts/check_secrets.py` 退出 0；`pip-audit` 因环境解析全量依赖树极慢（纯 CPU，运行约 36min / CPU 2157s 仍未出结果，块缓冲无中途输出），用户决定停止——`requirements.txt` 依赖版本与 `Makefile` 的 `PIP_AUDIT_IGNORE` 自上次成功跑通（退出 0，`No known vulnerabilities found, 2 ignored`）后未改动，故引用上次落盘证据（`reports/review-02.md` L42-46）；待网络/机器空闲时手动复跑 `make check-security` 取新鲜退出码即可完全闭合。详见 `docs/changes/course-submission-readiness/verification.md` 本次复跑表
- [x] 5.2 运行 `openspec validate --changes course-submission-readiness --strict`；验证：`1 passed, 0 failed`，退出 0（注意 validate 用复数 `--changes`）
- [ ] 5.3 【人工】补全 `report.md` 占位（成员分工、演示视频网盘链接、Harness 具体模型名、提交日期）；验证：`report.md` 无 `<!-- TODO -->` 残留，分工能对上仓库提交与 `reports/` 记录
- [ ] 5.4 【人工】录制 ≤3 分钟演示录屏（依次跑 `make check`、`make check-security` 展示全绿，再演示核心功能，可配字幕/快进），上传百度/北大网盘，把下载链接写入 `report.md` 头部；验证：链接可打开，视频 ≤3 分钟且验证命令真实跑过、结果可见
- [ ] 5.5 【人工】在 GitHub 仓库开启 `main` 分支保护（要求 CI status check 通过方可合入），把保护设置证据补入 `reports/`；验证：`main` 未通过 CI 的提交不可合入，证据可查
