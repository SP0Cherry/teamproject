## Purpose

为课程交付建立仓库级可验证的质量与证据契约：统一门禁命令的退出码语义、CI 与主干分支保护构成的合入门禁、`reports/` 下评审/三查/压测证据的归档与可复核性、七类核查清单的齐备性，以及交付报告 `report.md` 的结构与可查性。这些行为均可由命令执行或文件存在性验证，不涉及运行时业务接口。

## ADDED Requirements

### Requirement: 统一门禁命令与退出码语义

仓库根目录 SHALL 提供 `make check` 与 `make check-security` 两条命令。`make check` SHALL 覆盖后端单元与接口测试、端到端接口用例、前端测试以及覆盖率阈值检查；任一检查失败时 `make check` SHALL 以非零退出码结束，全部通过时 SHALL 退出 0。`make check-security` SHALL 覆盖依赖审计与密钥扫描；发现高危依赖或仓库中硬编码密钥时 SHALL 以非零退出码结束，未发现时 SHALL 退出 0。任一命令不得在失败时仍返回 0。

#### Scenario: 全部检查通过时 make check 退出 0

- **WHEN** 在仓库根目录执行 `make check`，且后端测试、端到端用例、前端测试与覆盖率阈值全部通过
- **THEN** 命令退出码为 0

#### Scenario: 存在失败检查时 make check 非零退出

- **WHEN** 执行 `make check` 时后端测试、端到端用例、前端测试或覆盖率阈值中任一项未通过
- **THEN** 命令以非零退出码结束，不掩盖失败

#### Scenario: 覆盖率低于阈值时被门禁阻断

- **WHEN** 执行 `make check` 时测试覆盖率低于设定阈值
- **THEN** `make check` 以非零退出码结束

#### Scenario: 安全扫描发现高危时 make check-security 非零退出

- **WHEN** 执行 `make check-security` 时发现高危依赖或硬编码密钥
- **THEN** 命令以非零退出码结束；未发现高危时退出 0

### Requirement: CI 与主干分支保护构成合入门禁

仓库 SHALL 配置持续集成，在向 `main` 分支的推送与针对 `main` 的拉取请求上自动运行 `make check` 与 `make check-security`。`main` 分支 SHALL 受分支保护，要求上述 CI 检查通过后方可合入；未通过的提交 SHALL 被阻断，不得合入 `main`。

#### Scenario: 拉取请求触发 CI 门禁

- **WHEN** 提交针对 `main` 的拉取请求
- **THEN** CI 自动运行 `make check` 与 `make check-security`，并将结果作为合入状态检查

#### Scenario: 门禁失败阻断合入

- **WHEN** 某提交的 CI 检查未通过
- **THEN** 该提交不得合入 `main`，状态检查显示失败

### Requirement: 评审证据归档与可复核

仓库 SHALL 在 `reports/` 目录归档不少于 3 份评审记录，每份为独立的 markdown 文件。每份记录 SHALL 写全四件事：用什么手段查、查了什么、判据是什么、结果是什么；其中不少于 2 份 SHALL 标注由 AI 自审或脚本发现。每份记录引用的命令 SHALL 可在仓库内复跑且退出码与记录一致，引用的文件路径 SHALL 真实存在；不得写「我觉得」这类无判据的结论。

#### Scenario: 评审记录数量与分布达标

- **WHEN** 清点 `reports/` 目录下的评审记录文件
- **THEN** 评审记录不少于 3 份，且其中不少于 2 份标注为 AI 自审或脚本发现

#### Scenario: 评审记录四件事齐全且可复核

- **WHEN** 抽查任一评审记录并执行其中引用的命令、打开引用的路径
- **THEN** 记录含手段/查了什么/判据/结果四件事，命令可复跑且退出码与记录一致，引用路径存在

### Requirement: 高风险三查记录

`reports/` SHALL 包含并发、事务、权限各一份高风险检查记录（`risk-concurrency.md`、`risk-transaction.md`、`risk-authz.md`），每条 SHALL 写全四件事并给出可复跑命令。并发检查 SHALL 验证同一操作并发投递多次只产生一份结果（幂等约束生效）；事务检查 SHALL 验证写入中断后不产生孤儿数据、状态一致；权限检查 SHALL 验证跨范围访问资源返回与不存在一致的拒绝（404）。

#### Scenario: 三查文件齐全

- **WHEN** 检查 `reports/` 目录
- **THEN** 存在 `risk-concurrency.md`、`risk-transaction.md`、`risk-authz.md` 三份文件

#### Scenario: 并发幂等可复跑验证

- **WHEN** 按 `risk-concurrency.md` 中的命令并发触发同一操作多次
- **THEN** 只产生一份结果，命令可复跑且退出码与记录一致

#### Scenario: 事务一致性可复跑验证

- **WHEN** 按 `risk-transaction.md` 中的命令注入写入中断
- **THEN** 不出现孤儿数据，前后状态一致，命令可复跑

#### Scenario: 越权访问被拒

- **WHEN** 按 `risk-authz.md` 中的命令以非授权身份访问他人/他组资源
- **THEN** 返回与不存在一致的 404 拒绝，命令可复跑

### Requirement: 七类核查清单齐备

仓库 SHALL 提供七类核查清单，覆盖接口入口、业务逻辑、数据库、公共函数、错误处理、安全、性能七类；每一类 SHALL 写清核查问题与检查手段，并指向仓库中真实存在的检查命令或用例路径。清单 SHALL 集中存放且可在一处打开数出七类。

#### Scenario: 七类齐全且每类有问题与手段

- **WHEN** 打开七类核查清单文件
- **THEN** 可数出接口入口、业务逻辑、数据库、公共函数、错误处理、安全、性能共七类，每类同时给出核查问题与检查手段

#### Scenario: 清单指向的检查真实存在

- **WHEN** 按清单中某一类的检查手段执行对应命令或打开对应用例路径
- **THEN** 命令可执行或路径存在，不是空指向

### Requirement: 压测报告与性能阈值

仓库 SHALL 提供可重放的压测脚本，并在 `reports/bench.md` 记录压测结果。报告 SHALL 写明固定环境、数据规模与脚本参数，并给出列表接口正向请求的 P95 时延与吞吐；列表接口正向 P95 SHALL 不超过 500ms，超过则性能验收不通过。压测 SHALL 可在断网下重放（不依赖外部服务）。

#### Scenario: 压测报告存在且含阈值对照

- **WHEN** 打开 `reports/bench.md`
- **THEN** 含环境/数据规模/参数、P95 与吞吐，以及与 500ms 阈值的对照结论

#### Scenario: 压测可断网重放

- **WHEN** 在断开外部网络的环境下按报告命令重放压测
- **THEN** 压测脚本可运行并产出结果，不访问真实外部服务

### Requirement: 交付报告结构与可查性

仓库根目录 SHALL 存在 `report.md`，其头部 SHALL 写明项目、成员分工、仓库地址、演示视频下载地址、使用的 Harness、支撑记录目录与提交日期；正文 SHALL 含六节（一句话介绍、AI 写了什么、审核记录、高风险三查、门禁与演示、复盘）。每节引用的文件 SHALL 写全路径且真实存在，引用的执行命令 SHALL 可直接复制运行；查不实的节不得声称已完成。

#### Scenario: report.md 头部与六节齐全

- **WHEN** 打开根目录 `report.md`
- **THEN** 头部含项目/分工/仓库地址/视频地址/Harness/支撑目录/提交日期，正文含六节

#### Scenario: 报告引用可查

- **WHEN** 抽查 `report.md` 中引用的文件路径与命令
- **THEN** 路径存在可打开，命令可直接复制执行
