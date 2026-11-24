## Context

见 proposal.md 的 Why。当前仓库经审计缺 `report.md`、`reports/`、`Makefile`、`.github/workflows/`、七类清单、并发测试、压测、覆盖率门禁；`README.md` 自承无统一业务门禁。既有 `docs/changes/audit-and-fix-prototype-bugs/audit-summary.md` 已把 `SEC-17（缺依赖漏洞扫描）`、`REV-05（无 CI 门禁）` 列为待补缺口，本变更直接闭环它们。

约束：
- 开发环境为 Windows，`make` 不在 PATH，但 Git for Windows 自带 `mingw32-make`（GNU Make 4.2.1）可用；CI 为 Linux，原生 `make` 可用。
- 后端测试跑内存 SQLite（`StaticPool`，`backend/tests/conftest.py`），向量检索在 SQLite 下回退无序（项目既有约定）；并发用例在 SQLite 上验证应用层幂等与唯一约束，真实多连接竞态以命令可复跑为准（TEST-01/04）。
- REV-02 手工维护文件 ≤15；本变更因课程 rubric 强制「一份记录一个文件」会触达上限，按 REV-06 登记例外。
- REV-07 要求证据归档到 `docs/changes/<变更名>/`，课程课件要求交付目录为 `reports/`——两套目录并存并交叉引用。
- 安全扫描遵循项目偏好：优先免 API 密钥、免额外服务的方案（参考联网搜索选型约定）。

## Goals / Non-Goals

**Goals:**
- 建立 `make check` / `make check-security` 统一门禁，退出码语义满足 spec「统一门禁命令与退出码语义」。
- 建立 GitHub Actions CI 在 PR/push to main 运行门禁；`main` 分支保护由人工开启。
- 在 `reports/` 产出七类核查清单、≥3 份评审（≥2 份机器发现）、三查记录、压测报告，全部可查可复跑。
- 新增并发幂等测试与覆盖率门禁，作为三查与门禁的复跑来源。
- 产出根级 `report.md`（六节 + 头部），并在 `README.md` 登记门禁命令。
- 在 `docs/changes/course-submission-readiness/` 归档变更证据（REV-07），登记 REV-02/REV-06 例外。

**Non-Goals:**
- 不修改任何运行时业务行为、接口契约、数据模型或迁移（并发测试只验证既有幂等）。
  - **apply 阶段修正**：实跑并发用例发现 `confirmation_key` 幂等在并发下失效（TOCTOU，8 并发确认产生 16 条），违反 spec「只产生一份结果」的强制要求。原假设「既有幂等并发安全」不成立。为满足已批准的 spec 契约，本变更追加决策 11 的最小硬化（逐事项唯一键 + unique 索引 + IntegrityError 回退），属修复既有缺陷而非新增行为；除此之外仍不修改业务行为/接口契约。
- 不录制演示录屏、不操作 GitHub 分支保护设置（须人工完成，tasks 中标为人工项）。
- 不补齐 audit-summary 中其余后续缺口（分页、限流、指标监控、备份留痕等），它们超出课程交付范围。
- 不引入需 API 密钥或常驻服务的安全扫描。

## Decisions

### 决策 1：Makefile 为统一门禁入口，Windows 经 mingw32-make 调用

**选择**：根目录新建 GNU `Makefile`，提供 `check`、`check-security`、`bench` 目标。`check` 顺序执行：后端 `pytest`（含 `--cov --cov-fail-under`）→ `apitest/run_all.py` → 前端 `npm test`；任一非零即整体非零（`make` 默认遇错停止）。`check-security` 执行 `pip-audit` 与仓库内置密钥扫描脚本。

**理由**：课程硬性要求 `make check` 命令存在且红即挡住。CI（Linux）原生 `make` 可直接调用；本地 Windows 用 `mingw32-make check`。recipe 每行用 `cd <dir> && <cmd>` 单行写法，兼容 cmd.exe 与 bash，避免 shell 方言差异。

**备选**：用 PowerShell 脚本或 `package.json` script 代替 Makefile——不满足课程「`make check`」命令契约。

### 决策 2：CI = GitHub Actions，主干保护人工开启

**选择**：新建 `.github/workflows/ci.yml`（ubuntu-latest），on: push 到 main + pull_request；步骤：checkout → setup-python 3.11 → setup-node → 安装后端/前端依赖 → `make check` → `make check-security`，任一步失败即 workflow 失败。`main` 分支保护（Settings → Branches → 要求 status check 通过）由用户在 apply 后手动开启，并在 `reports/` 留截图/说明证据。

**理由**：课件明确「`make check` 挂进 CI 与 main 保护才叫门禁」。GitHub Actions 免配置、与仓库同源；分支保护是仓库设置，无法由代码变更自动落地。

**备选**：其他 CI 平台——仓库在 GitHub（`https://github.com/SP0Cherry/teamproject`），Actions 最直接。

### 决策 3：check-security 用 pip-audit + 内置密钥扫描，零 API 密钥

**选择**：`make check-security` = ① `python -m pip_audit -r backend/requirements.txt --desc`（有高危/严重则非零；首次需联网拉取漏洞库，CI 满足）；② `python scripts/check_secrets.py`（内置纯脚本，扫描 git 跟踪文件中的硬编码密钥特征——JWT_SECRET 非空默认值、私钥、token 字面量——排除 `.env`（已 gitignore）与测试替身，命中则非零）。两者都免 API 密钥、免常驻服务。

**理由**：项目偏好免密钥免费方案（既有约定）；`pip-audit` 是 Python 生态官方推荐，`check_secrets.py` 自包含可断网重放。

**备选**：`gitleaks`（需下载二进制）、`trivy`（需安装）、`safety`（需 key/额度）——引入额外安装成本，违背免配置偏好。

### 决策 4：reports/ 与 docs/changes/ 双目录并存，交叉引用

**选择**：`reports/` 是面向课程评分的交付目录（`checklist.md`、`review-0X.md`、`risk-*.md`、`bench.md`），路径与课件要求完全一致，报告中引用 `reports/xxx.md` 可直接打开。`docs/changes/course-submission-readiness/` 是项目侧变更归档（REV-07），放本变更的说明、验证记录、评审结论与例外登记。两目录互相链接：`report.md` 与 `reports/` 指向 `docs/changes/...` 的完整归档，归档文件反向列出 `reports/` 清单。

**理由**：课程与项目规范对证据存放位置要求不同，互不替代；并存既满足评分可查，又不破坏 REV-07 归档习惯。

### 决策 5：并发测试放 backend/tests，验证既有幂等，SQLite  caveat 显式记录

**选择**：新增 `backend/tests/test_concurrency_confirmation.py`，用 `asyncio.gather` 并发对同一通知触发 N 次确认，断言只生成一条待办（`confirmation_key` 幂等生效）；复用 `conftest.py` 的隔离 SQLite fixture（TEST-04）。复跑命令写入 `reports/risk-concurrency.md`：`cd backend && python -m pytest tests/test_concurrency_confirmation.py -q`。

**理由**：`notification-intake`/`task-planning` 规约已要求确认幂等，本测试只验证不改变行为（对应 proposal「无 Modified Capability」）。SQLite 单一 `StaticPool` 连接不能完美模拟多连接竞态，但能验证应用层去重与唯一约束逻辑，且命令可复跑——满足课程「命令可复跑」要求。caveat 写入 `risk-concurrency.md`，不夸大覆盖。

**备选**：在 apitest 用真实 Postgres 做并发——更真实但重，且现有 apitest 用隔离 SQLite；为保持离线可重放与一致性，选 pytest 方案。

### 决策 6：压测脚本用真实 uvicorn + 隔离 SQLite + stub 模型，写 reports/bench.md

**选择**：新建 `scripts/bench.py`，沿用 `apitest/run_all.py` 的模式：起一个绑定 127.0.0.1 的真实 uvicorn 后端（隔离 SQLite、stub LLM、不连业务库/真实模型），建合成账号与少量待办，用 `httpx` 并发对 `GET /api/v1/todos`（代表性列表接口）发压，统计 P95 与吞吐，断言 P95 ≤ 500ms（OPS-09），把参数、环境、结果与阈值对照写入 `reports/bench.md`（带时间戳）。`make bench` 调用它。

**理由**：真实 HTTP 栈 + 隔离依赖 = 结果可信且断网可重放（TEST-05）；列表接口对应 OPS-09 的 500ms 预算；`reports/bench.md` 直接成为课程交付证据。

**备选**：in-process ASGITransport 压测——更轻但绕过 HTTP 栈，时延偏低，说服力弱；用 k6——需额外安装，项目无 Node 压测先例。

### 决策 7：覆盖率门禁用 pytest-cov + fail-under，阈值起步适中

**选择**：`backend/requirements-dev.txt` 加 `pytest-cov`；`backend/pytest.ini` 追加 `addopts = --cov=app --cov-report=term-missing --cov-fail-under=60`（起步阈值 60%，apply 时按实际覆盖率微调，不得为过线而删测试）。`make check` 的 pytest 步骤即带上覆盖率检查。

**理由**：TEST-06/REV-05 要求门禁含覆盖率阈值；60% 是可达成的起步线，避免一开始就因阈值过高门禁常红而被绕过（REV-05 禁止放宽检查变绿）。

### 决策 8：评审记录从真实审计材料提炼 + 真实红→绿，不编造

**选择**：`reports/review-0X.md` 基于 `docs/changes/audit-and-fix-prototype-bugs/` 的真实审计结论提炼：review-01（AI 自审发现，如 AI-05/AI-06 校验缺口）、review-02（脚本发现，如 TEST-12 回归用例红→绿，或本变更新增并发测试的首跑结果）、review-03（人工确认，如本变更对「SEC-17/REV-05 缺口是否已由门禁闭环」的判定）。每份写全四件事并给出可复跑命令。apply 时实际跑命令、把真实退出码/结果写入，不写模板话。

**理由**：REV-03 禁止「只留一句已检查」；课程第 3 节 0 分情形是「事后补的模板话」。必须用真实材料与真实执行结果。

### 决策 9：report.md 自动生成结构，用户专有字段留占位

**选择**：生成 `report.md` 全文骨架并填好已知项（项目描述取自 README、仓库地址、技术栈、AI 产出清单指向真实路径、门禁命令、三查命令）；对用户专有且我无法获知的字段（成员分工、演示视频网盘链接、Harness 的具体模型名、提交日期）留 `<!-- TODO: 由组员填写 -->` 显式占位，apply 末尾提示用户补全。

**理由**：这些字段只能由用户提供，不能编造；占位明确，避免报告被当作「已完成」提交。

### 决策 10：REV-02 例外登记

**选择**：本变更新增/修改的手工维护文件约 15–18 件，超出 REV-02 的 15 件上限，原因是课程 rubric 强制 `reports/` 下「一份记录一个文件」（3 评审 + 3 三查 + bench + checklist = 8 个证据文件），非无关扩张。在 `docs/changes/course-submission-readiness/record.md` 的「例外登记（REV-06）」节登记：范围、理由、风险、替代控制（每份文件精简、内容可交叉验证）、责任人、批准人、到期日。

### 决策 11：硬化确认幂等以满足 spec 并发绿灯（apply 阶段发现并修复）

**背景**：按决策 5 写出并发用例后首跑即红——对同一通知并发 8 次确认产生了 16 条待办（8×2），而非 2 条。根因是 `ConfirmationService.confirm` 采用 check-then-create：先 `list_by_confirmation_key` 查到空再插入，无唯一约束、无行锁，并发下所有请求在任一请求提交前都查到空，于是全部插入（TOCTOU）。spec「高风险三查」强制要求并发检查「只产生一份结果，命令可复跑且退出码与记录一致」，故必须修复至绿灯，不能以 caveat 搪塞红灯。

**选择**（最小、正确、可逆）：
1. `confirmation_key` 由「批次共享键」改为「逐事项唯一键」：`notif:{notification_id}:user:{user_id}:item:{i}`。同一批次的不同事项 index 不同 → 不互相冲突；同一批次重放产生相同 key → 被唯一索引挡住。
2. `todos.confirmation_key` 加 `unique=True`（模型 + 迁移 `0017_*` 把既有非唯一索引转为唯一索引）。列可空，NULL 允许多个（Postgres/SQLite 均视 NULL 互异），不影响非确认来源的待办。
3. 「批次是否已存在」查询改为按批次前缀 `notif:{nid}:user:{uid}:item:%` 做 like（repo 新增 `list_by_confirmation_batch`）；UUID 不含通配符与冒号，前缀无歧义。
4. `confirm` 把 create+commit 包进 `try/except IntegrityError`：捕获后 `rollback`，再按批次前缀重查并返回胜方批次——真正并发安全的幂等（race loser 不报错、不造重复）。
5. 并发用例改为「每请求独立 session」建模生产（共享同一 in-memory SQLite，StaticPool 单连接由 aiosqlite 串行化写入），不再用共享单 session（后者会累积 pending 对象，不能真实建模并发事务）。

**理由**：唯一索引是数据库层最后防线，`IntegrityError` 回退是标准幂等写法；逐事项键保留了多事项批次能力（唯一约束挡的是「重放的同事项」，不是「同批次的不同事项」）。修复后用例由红转绿，恰好构成课程第 5 节要求的「门禁红→绿证据」。

**备选**：单独建 `confirmation_batches` 表（unique(notif,user)）——更范式化但改动更大；`SELECT FOR UPDATE` 锁通知行——Postgres 有效但 SQLite 忽略，无法在离线测试中验证，故不选。

**回滚**：纯新增迁移 + 服务分支，downgrade 可逆；不影响既有串行幂等行为。

## Risks / Trade-offs

- **[Windows 本地 make 不在 PATH]** → `make check` 本地需用 `mingw32-make check`；README 明确写明，CI 不受影响。若用户希望 `make` 直接可用，自行把 Git 的 `mingw32-make.exe` 目录加入 PATH 或起别名。
- **[pip-audit 首次需联网拉漏洞库]** → 本地断网时 `check-security` 的 pip-audit 步骤可能失败；密钥扫描 `check_secrets.py` 可断网运行。CI 有网，满足评分；README 标注此依赖。
- **[SQLite 并发覆盖度弱于 Postgres]** → `risk-concurrency.md` 显式记录 caveat，不声称覆盖了多连接真实竞态；如后续要更强覆盖，可追加 Postgres 版用例（非本变更范围）。
- **[覆盖率阈值 60% 可能首跑即红]** → 若实际覆盖率低于 60%，apply 时优先补测试而非调低阈值（REV-05）；若补测后仍略低，可据实测在合理区间内定阈值并记录理由，不得为过线删用例。
- **[演示录屏与分支保护依赖人工]** → 这两项无法自动完成，tasks 中明确标为人工项并给操作步骤；未完成前第 5 节不能声称满分。
- **[report.md 含未填占位]** → 用户提交前必须补全分工/视频/模型/日期，否则「每节都要能查」可能因头部不全扣分；apply 末尾给出核对清单。

## Migration Plan

无运行时部署，故无线上迁移/回滚。落地顺序（apply 阶段执行）：

1. 建 `Makefile`、`.github/workflows/ci.yml`、`scripts/check_secrets.py`、`scripts/bench.py`、覆盖率配置——先把门禁立起来。
2. 新增 `backend/tests/test_concurrency_confirmation.py`，本地跑通。
3. 实跑 `make check` / `make check-security` / `make bench`，捕获真实输出；用真实结果写 `reports/` 全部证据文件与 `reports/checklist.md`。
4. 写 `report.md`（用户字段留占位）、更新 `README.md` 门禁登记、建 `docs/changes/course-submission-readiness/` 归档（含例外登记）。
5. 交付用户人工清单：填 `report.md` 占位 → 录屏并上传 → 开 main 分支保护 → 把录屏链接与保护证据补入 `reports/`。
6. 跑 `openspec validate`，通过后等用户触发 apply→archive。

回滚：纯新增文件，删除本变更新增文件即可撤销，不影响既有业务代码。

## Open Questions

- 覆盖率阈值的精确值（60% 起，apply 时按实测微调）与压测并发数/时长——不影响 spec、方案与任务拆分，apply 时据实测定。
- `main` 分支保护的具体合入策略（是否要求线性历史、是否允许管理员绕过）——由用户在 GitHub 设置时决定，不影响本变更代码产物。
