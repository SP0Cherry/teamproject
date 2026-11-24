# 门禁拦截记录：CI 先红后绿（course deliverable §⑤）

## 结论

统一门禁在 CI（`.github/workflows/ci.yml`，job `quality-gate`）中真实执行过 `make check` 与 `make check-security`。首次推送即被 `make check` 挡下（退出码 2），定位并修复后同一门禁转绿。

## 证据（两次运行）

| 轮次 | 提交 | 运行链接 | `make check` | `make check-security` | 结论 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| #1 | `2ff364e` | https://github.com/SP0Cherry/teamproject/actions/runs/45386750679 | **失败，退出码 2** | 未执行（前序失败即跳过） | 红 |
| #2 | `3b4b2b2` | https://github.com/SP0Cherry/teamproject/actions/runs/45387262003 | 成功，退出码 0 | 成功，退出码 0 | 绿 |

- 失败步骤的 GitHub 注解：`Process completed with exit code 2.`
- 判断依据：`make` 的任一子命令非零即整体非零（见 `Makefile` 注释与 `README.md`「统一交付门禁」）。

## 根因

`backend/tests/test_migrations.py` 在模块顶层执行 `from embedded_postgres import PostgresServer`。`embedded-postgres` 是本地迁移验证工具，不在 `backend/requirements.txt` / `requirements-dev.txt` 中。CI 全新环境安装的是 requirements 集合，缺少该包，pytest 在**测试收集阶段**即报 `ModuleNotFoundError`，pytest 以退出码 2 结束，`make check` 随之中断。

说明：这不是用例失败，而是收集期导入失败；因此 CI 中 `make check-security` 也被 `make` 的失败即停语义正确跳过。

## 修复

提交 `3b4b2b2`（`fix(test): 迁移检查可选依赖缺失时不再导致 pytest 收集失败`）：

- 将 `embedded_postgres` 改为可选导入（`try/except ImportError`），使 pytest 收集不再崩溃；
- 在 `main()` 入口保留显式检查：缺少依赖时抛出 `RuntimeError`，提示安装 `embedded-postgres==18.6.3`。即“手动跑迁移校验仍明确失败”，不静默跳过、不降低证据强度。
- 本地校验：`cd backend && python -m pytest --collect-only -q` → `160 tests collected`，无收集错误。

## 复跑命令

```bash
# 与 CI 一致（Linux）
make check
make check-security

# Windows 本地（Git for Windows 自带 make）
mingw32-make check
mingw32-make check-security
```

## 边界说明（如实记录）

- 本次两次运行证明的是：**CI 能真实执行门禁并拦住失败的提交（红），修复后转绿**。
- 提交 `2ff364e` 是在分支保护尚未配置为“必需状态检查”之前直接推送到 `main` 的，因此这次红是“推送后 CI 报红”，尚不构成“PR 因 CI 未通过而禁止合并”的截图证据。
- `main` 分支保护已启用（禁止强推/删除、要求 PR），但“Require status checks → `quality-gate`”需在 GitHub 设置中开启后，才会真正阻断合入。开启后建议补一次“失败 PR 被禁止合并”的截图，作为 §⑤ 的完整门禁证据。

## 关联

- 门禁定义：`Makefile`、`.github/workflows/ci.yml`
- 门禁说明：`README.md`「统一交付门禁（delivery-gate）」
- 同类红→绿记录：`reports/review-02.md`（并发幂等、依赖漏洞）
- 课程报告引用：`report.md` 第 ⑤ 节
