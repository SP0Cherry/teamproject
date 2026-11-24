# 七类核查清单（delivery-gate）

本清单对应课程评分第 ② 节要求的七类核查。每类给出核查问题、检查手段、复跑命令与证据路径。所有命令在仓库根执行；Windows 本地用 `mingw32-make`，Linux/CI 用 `make`。

## 1. 接口入口

- **核查问题**：所有 HTTP 路由是否被端到端覆盖、入口鉴权是否生效、异常输入是否被拦截。
- **检查手段**：后端 pytest（`backend/tests/`，含鉴权/路由）+ apitest 端到端 harness（`apitest/`，真实 ASGI 子进程 + stub LLM + 真实 mcp-server）。
- **复跑命令**：`make check`（依次跑 pytest → apitest → 前端测试）。
- **证据**：`make check` 退出 0；pytest `160 passed`；apitest `总计 46 项，通过 46，失败 0`。

## 2. 业务逻辑

- **核查问题**：通知确认、待办状态流转、提示词解析等核心业务逻辑是否正确且幂等。
- **检查手段**：`backend/tests/test_confirmation.py`、`test_todo_parser.py`、`test_concurrency_confirmation.py` 等业务用例。
- **复跑命令**：`cd backend && python -m pytest tests/test_confirmation.py tests/test_concurrency_confirmation.py -q`。
- **证据**：串行幂等 `test_confirm_is_idempotent` 通过；并发幂等 `test_concurrent_confirm_produces_single_batch` 通过（详见 `reports/risk-concurrency.md`）。

## 3. 数据库

- **核查问题**：模型约束、迁移一致性、确认幂等的唯一索引是否生效。
- **检查手段**：`backend/tests/test_migrations.py`（迁移校验，需 embedded PostgreSQL）；模型层 `Base.metadata.create_all` 在测试库自动建唯一索引；迁移 `backend/alembic/versions/0017_todo_confirmation_key_unique.py`。
- **复跑命令**：`cd backend && python -m pytest tests/test_concurrency_confirmation.py -q`（验证唯一索引在 create_all 库生效）；迁移链 `cd backend && python -m alembic heads`。
- **证据**：`alembic heads` 输出 `0017_todo_confirmation_key_unique (head)`；并发用例绿灯证明唯一索引生效。

## 4. 公共函数（覆盖率门禁）

- **核查问题**：公共代码是否被测试覆盖到设定阈值，避免未测代码合入。
- **检查手段**：`pytest-cov`，`backend/pytest.ini` 配置 `--cov=app --cov-report=term-missing --cov-fail-under=60`；低于 60% 则 pytest 退出非零，门禁失败。
- **复跑命令**：`make check`（pytest 阶段会打印覆盖率并执行阈值判定）。
- **证据**：`Required test coverage of 60% reached. Total coverage: 78.90%`，`160 passed`。阈值未为过线而调低（REV-05）。

## 5. 错误处理（故障注入）

- **核查问题**：下游不可达、错误令牌、模型异常等故障是否被隔离且不阻断主流程。
- **检查手段**：apitest harness 注入故障场景（连接不可达服务器、错误令牌、模型 error 调用）并断言可见且不阻断。
- **复跑命令**：`make check`（apitest 阶段）。
- **证据**：apitest 包含 `连接不可达服务器 -> status=error 且不阻断`、`错误令牌连接 -> status=error`、`QA SSE：error 调用在 meta 可见` 等用例，均 PASS。

## 6. 安全

- **核查问题**：是否泄露密钥、是否存在可利用的依赖漏洞。
- **检查手段**：`scripts/check_secrets.py`（扫描 git 跟踪文件中的私钥/令牌/密钥赋值）+ `pip-audit`（依赖漏洞扫描）。两者由 `make check-security` 串联，任一非零则门禁失败。
- **复跑命令**：`make check-security`。
- **证据**：`OK: no hardcoded secrets found`；`No known vulnerabilities found, 2 ignored`。两条例外（`PYSEC-2026-4298`、`PYSEC-2026-1325`）均无修复版本且经评估在本应用不适用（见 `reports/review-03.md`），已在 `Makefile` `PIP_AUDIT_IGNORE` 登记。pip-audit 首次运行需联网拉取漏洞库。

## 7. 性能

- **核查问题**：列表接口 P95 是否 ≤ 500ms（OPS-09）。
- **检查手段**：`scripts/bench.py`（进程内 ASGITransport，隔离 SQLite，20 并发 × 200 请求预热 10）。
- **复跑命令**：`make bench`（可断网重放）。
- **证据**：`reports/bench.md`：P95=201.78ms ≤ 500ms，rps=105.7，all_200=True，结论通过。注：基准不含 TCP/uvicorn 调度开销，P95 为保守下界。
