# 审核记录 01：AI 自审发现（SEC-17 / REV-05 闭合）

## 手段
AI 按项目八类规范对仓库做全量审计，产出 `docs/changes/audit-and-fix-prototype-bugs/` 下 8 份领域审计（产品/后端/安全/测试/数据/AI/运维/评审）及汇总 `docs/changes/audit-and-fix-prototype-bugs/audit-summary.md`。本记录针对汇总中标记为「后续变更」的缺口，核验本变更是否闭合。

## 查了什么
`audit-summary.md` 的「后续变更」表明确列出两项与交付门禁相关的缺口：
- **SEC-17**：缺少依赖漏洞扫描，需配置 CI 扫描。
- **REV-05**：无 CI 门禁，DevOps 建设。

核验本变更 `course-submission-readiness` 是否新增了对应能力并纳入统一门禁。

## 判据
- SEC-17：存在一条可复跑的依赖漏洞扫描命令，且被纳入 `make check-security`；密钥泄露扫描同步纳入。
- REV-05：存在 CI workflow，在 push/PR 时运行门禁，且可配置为分支保护的 required check。

## 结果
两项缺口均已闭合：
- 新增 `Makefile` 目标 `check-security`：`pip-audit -r requirements.txt` + `python scripts/check_secrets.py`。
- 新增 `.github/workflows/ci.yml`：在 push 到 `main` 与 PR 时执行 `make check` 与 `make check-security`。
- 实跑 `make check-security` 退出 0（`No known vulnerabilities found, 2 ignored` + `no hardcoded secrets found`）。

## 复跑命令
```bash
make check-security          # Linux / CI
mingw32-make check-security  # Windows（Git for Windows 自带）
```
首次运行 `pip-audit` 需联网拉取漏洞库。

## 关联
- 审计源材料：`docs/changes/audit-and-fix-prototype-bugs/audit-summary.md`、`docs/changes/audit-and-fix-prototype-bugs/audit-security.md`、`docs/changes/audit-and-fix-prototype-bugs/audit-operations.md`
- 本变更归档：`docs/changes/course-submission-readiness/`
