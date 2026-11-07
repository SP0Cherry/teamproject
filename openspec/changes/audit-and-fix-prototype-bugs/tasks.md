## 1. 八类规范合规审计

- [x] 1.1 审计产品规范（PROD-01 至 PROD-13）：对照 `frontend/src/views` 与路由，核查页面入口、响应式、空状态与可达性，输出合规清单至 `docs/changes/audit-and-fix-prototype-bugs/audit-product.md`，验证每条标准有"符合/不符合/不适用"判定与证据。
- [x] 1.2 审计后端规范（BE-01 至 BE-16）：检查 `backend/app` 分层、接口命名、错误码、参数校验、事务边界、幂等、分页与日志，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-backend.md`，验证仓储层无业务逻辑、接口层无 SQL、错误码符合 BE-04。
- [x] 1.3 审计安全规范（SEC-*）：检查认证、授权、文件上传、外部输入、会话与敏感数据处理，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-security.md`，验证密钥不入库不进日志、上传有类型校验、接口按身份授权。
- [x] 1.4 审计测试规范（TEST-*）：检查 `backend/tests` 覆盖核心业务规则、幂等、并发与依赖失败，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-testing.md`，验证存在通知确认、组同步、权限隔离的自动化测试。
- [x] 1.5 审计运维规范（OPS-01 至 OPS-11）：检查 `docker-compose.yml`、`Dockerfile`、健康检查与配置外置，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-operations.md`，验证环境变量从 `.env.example` 可知、服务有健康检查端点。
- [x] 1.6 审计 AI 规范（AI-01 至 AI-10）：检查提示词版本、模型参数、输出校验、降级与用量记录，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-ai.md`，验证模型输出经 schema 校验、失败有降级、提示词在仓库内。
- [x] 1.7 审计数据规范（DATA-*）：检查数据模型、迁移、索引、缓存与留存策略，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-data.md`，验证迁移版本化、枚举统一、向量切片随版本清理。
- [x] 1.8 审计评审规范（REV-*）：检查变更记录、验收证据与完成定义，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-review.md`，验证本变更 artifacts 完整、任务可验证。
- [x] 1.9 汇总审计缺口：将八类审计中"不符合"项分类为"本次修复"与"后续变更"，输出 `docs/changes/audit-and-fix-prototype-bugs/audit-summary.md`，验证每条缺口有归属与处理计划。

## 2. 侧边栏收起缺陷修复

- [x] 2.1 修复 `WorkspaceLayout.vue` 重复 `.main` CSS 规则：删除约第 230 行的重复 `.main` 定义，保留含 `transition: margin-left 0.2s` 的规则，验证桌面端点击收起按钮后主内容区 `margin-left` 从 240px 过渡到 0。
- [x] 2.2 校验侧边栏状态绑定：确认 `:class="{ open: sidebarOpen }"` 与 `:class="{ 'sidebar-collapsed': !sidebarOpen }"` 在收起/展开时正确切换，验证移动端点击菜单按钮显示遮罩、点击遮罩收起。
- [x] 2.3 桌面端手动验证：在浏览器宽度 ≥ 768px 时点击收起按钮，验证侧边栏移出可视区且主内容区占满宽度；再次点击恢复展开。
- [x] 2.4 移动端手动验证：在浏览器宽度 < 768px 时点击菜单按钮，验证侧边栏覆盖展开并显示遮罩，点击导航项或遮罩后收起。

## 3. LLM 待办解析召回率提升

- [x] 3.1 增强 `TODO_PROMPT`：在 `backend/app/services/todo_parser.py` 中补充 2-3 个 few-shot 示例（多事项拆分、中文时间、地点、null 字段），明确要求不丢项，验证提示词包含示例且输出仍为严格 JSON。
- [x] 3.2 扩展 `validate_output` 深度校验：在 `backend/app/services/model.py` 中支持 `items` schema 校验，逐项检查 `title` 必填为字符串、其余字段为字符串或 null，验证不合规项被剔除但解析不中断。
- [x] 3.3 LLM 失败回退规则解析：修改 `parse_todos`，当 `chat_completion` 抛 `ModelError` 或 JSON 解析失败时调用 `_demo_parse` 并标记 `parser: "rule"`，验证 LLM 不可用时接口返回 200 且 parser 为 rule。
- [x] 3.4 漏项兜底：若 LLM 返回空 `todos` 但输入按分隔符切分后多片段，自动回退规则解析，验证输入"明天开会，后天交报告"返回至少 2 条候选。
- [x] 3.5 补充测试用例：在 `backend/tests/` 新增待办解析测试，覆盖多事项中文文本、字段缺失、LLM 失败回退、规则解析兜底，验证 `pytest backend/tests/` 通过。

## 4. 验证与交付

- [x] 4.1 运行后端测试：`pytest backend/tests/ -v`，验证全部测试通过且无新增失败。
- [x] 4.2 运行前端构建：`npm run build`（在 `frontend/` 目录），验证 TypeScript 编译与构建无错误。
- [x] 4.3 端到端验证解析流程：启动服务，通过前端"添加待办"输入复杂多事项文本，验证解析结果覆盖全部事项且标注 parser 来源。
- [x] 4.4 部署并验证：`docker compose up -d --build`，验证侧边栏收起与解析功能在线上容器正常工作，`docker compose logs api` 无异常。
- [x] 4.5 审计缺口弥补：对审计中"本次修复"类缺口（如错误码不规范、日志脱敏、参数校验缺失）进行修复，验证修复后对应审计条目改为"符合"。
