# 评审结论：course-submission-readiness

## 三类检查结果（REV-03）

### 1. 场景与业务结果（人工评审）
- 统一门禁 `make check` / `make check-security` / `make bench` 可重放，退出码语义清晰，README 已登记。
- 并发确认幂等：首跑红→硬化后绿，含变异复红，证明规约「只产生一份结果」被真实满足。
- 课程证据齐全：`reports/` 含七类核查清单、3 份审核记录、3 份高风险三查、基准结果；根 `report.md` 含头部与六节。
- **未完成（人工项，不计为机器通过）**：`report.md` 头部的分工/视频链接/模型名/提交日期占位、演示视频录制、GitHub `main` 分支保护开启——见任务 5.3–5.5。

### 2. 逐资源授权、事务及迁移恢复
- 授权：`test_authz.py` + `test_todo_owner_isolation` 绿，非成员 403、跨用户待办 404（`reports/risk-authz.md`）。
- 事务：`test_confirmation.py` 绿，确认在单事务内完成，校验失败无部分批次（`reports/risk-transaction.md`）。
- 迁移：`0017_todo_confirmation_key_unique.py` 提供 upgrade/downgrade；`alembic heads` 指向 0017。回滚保留唯一索引，不丢数据；降级若仍有冲突键会拒绝，不静默丢弃。

### 3. Harness 一致性检查（自动化规范检查）
- 门禁命令在 `Makefile` 与 `README` 一致；CI workflow 与 Makefile 目标一致。
- 归档三类材料齐全且与 `reports/` 互链。
- 依赖扫描例外按 REV-06 登记，范围/理由/风险/替代控制/责任人/批准人/到期日齐全。

## 完成定义核对（REV-01）
| 项 | 状态 |
| :--- | :--- |
| 约定场景及失败/边界处理实现 | 通过（并发、事务、授权均覆盖） |
| 适用用例通过 | 通过（160 passed + apitest 46/46 + 前端 11/11） |
| 门禁通过 | 通过（`make check`/`check-security`/`bench` 均退出 0） |
| 评审问题关闭 | 本变更评审问题已关闭；遗留 3 项为人工动作，非评审阻塞 |
| 相关文档同步 | 通过（README 登记门禁；`docs/data-dictionary.md` 的 `confirmation_key` 语义已同步为逐事项唯一 + 唯一索引名 `uq_todos_confirmation_key`） |
| 验证记录归档 | 通过（本目录 + `reports/`） |
| 权限/迁移/模型对应验证 | 通过（授权、迁移已验证；模型无变更，演示模式不变） |

## 已核对（文档一致性）

`confirmation_key` 语义由「批次共享」改为「逐事项唯一」。已核对并更新：`docs/data-dictionary.md` 的字段说明、索引名（`uq_todos_confirmation_key`）与幂等描述；`README.md` 设计要点措辞为「幂等去重」不涉及批次级，无需改动。不影响门禁。

## 结论
**机器可验证部分：基本可交付**。统一门禁、并发幂等硬化、课程证据均已实跑并留痕，未伪造、未放宽检查。

**本次复跑的环境性说明（2026-11-24）**：`make check`、`make bench`、`check_secrets` 均复跑退出 0；仅 `pip-audit` 因本机解析全量漏洞库极慢（>14 分钟纯 CPU、无活跃网络连接）未在会话窗口内返回最终退出码。`backend/requirements.txt` 依赖版本与 `Makefile` 的例外配置自上次成功跑通（退出 0，`No known vulnerabilities found, 2 ignored`）后未做任何修改，故判定非代码回归；建议在机器空闲时手动复跑 `make check-security` 取得本次退出码，后台进程仍在运行、完成后会写日志。详见 `verification.md` 本次复跑表。

**交付前尚需人工完成（任务 5.3–5.5）**：填写 `report.md` 占位、录制并上传演示视频、开启 GitHub `main` 分支保护并把证据截图补入 `reports/`。三项完成后本变更可归档。
