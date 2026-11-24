# 个人日常助手

个人日常助手：注册登录、通知解析与人工确认、待办、资料管理、AI 问答、日报和提醒。支持小组创建与加入、组内资料共享及组通知发布。

## 用户与场景

| 角色 | 触发操作 | 能力 | 承载页面 |
| :--- | :--- | :--- | :--- |
| 普通用户 | 注册/登录 | 账号认证 | 登录 |
| 普通用户 | 查看首页 | 今日/逾期/未来待办、日报 | 首页 |
| 普通用户 | 输入文本/上传文件 | AI 解析待办候选并人工确认 | 添加待办 |
| 普通用户 | 查看日程 | 周日历视图与待办列表 | 日程 |
| 普通用户 | 导入通知文件 | 通知解析与确认生成待办 | 通知导入 |
| 普通用户 | 上传资料 | 个人资料管理与向量化索引 | 资料 |
| 普通用户 | 提问 | 基于个人/小组资料的 AI 问答 | 问答 |
| 普通用户 | 创建/加入小组 | 小组协作、资料共享、组通知 | 小组 |
| 管理员 | 发布组通知 | 向组成员投递通知 | 小组 |

## 页面清单

| 页面 | 路由 | 功能 |
| :--- | :--- | :--- |
| 登录 | `/login` | 注册、登录 |
| 首页 | `/` | 今日待办、日报、快捷入口 |
| 通知导入 | `/notifications/import` | 上传通知文件、AI 解析、人工确认 |
| 日程 | `/schedule` | 周日历 + 待办列表、完成/恢复 |
| 添加待办 | `/todos/add` | 文本/文件解析、批量确认入库 |
| 资料 | `/attachments` | 上传、列表、编辑版本、删除、索引 |
| 小组 | `/groups` | 创建/加入、组列表（描述/成员数/角色/同步状态） |
| 小组详情 | `/groups/:id` | 组信息与邀请令牌、成员管理、同步开关、组通知发布/列表/撤回、组资料上传/列表/删除 |
| 问答 | `/qa` | 基于资料的 AI 问答与来源追溯 |

## 术语表

| 术语 | 含义 |
| :--- | :--- |
| 待办 (Todo) | 用户确认入库的任务，含标题、截止时间、地点、注意事项 |
| 候选 (Candidate) | AI 解析出的待办草稿，需用户确认后才入库 |
| 通知 (Notification) | 外部导入的消息，经解析后生成待办候选 |
| 确认 (Confirm) | 用户审核候选并提交入库的操作，事务内幂等 |
| 小组 (Group) | 多人协作空间，支持资料共享和通知发布 |
| 同步开关 (Sync) | 成员按组选择是否将新组通知同步到个人待办 |
| 演示模式 (Demo Mode) | 模型环境变量为空时使用规则解析，无外部 LLM 调用 |
| 解析来源 (Parser) | 待办解析的来源标识：LLM 或 rule（规则） |

## 技术栈

- 后端：FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL + pgvector
- 前端：Vue 3 + TypeScript + Vite + Pinia
- 认证：Argon2id 密码哈希 + JWT + 轮换刷新令牌 + HttpOnly Cookie
- 基础设施：Docker Compose

## 快速开始

### Docker Compose

```bash
docker compose up --build
```

服务地址：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- 健康检查：http://localhost:8000/healthz

### 本地开发

#### 后端

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt -r requirements-dev.txt

# 运行迁移
alembic upgrade head

# 启动（端口 8001 避免冲突）
uvicorn app.main:app --reload --port 8001
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

### 环境变量

复制 `.env.example` 为 `.env` 并修改：

- `DATABASE_URL`：PostgreSQL 连接串
- `JWT_SECRET`：JWT 签名密钥
- `SOURCE_SECRETS`：通知来源共享密钥（JSON）
- `MAX_UPLOAD_MB`：单文件上传上限（MB）
- 模型相关变量留空则进入演示模式（无外部调用）
- `AGENT_MAX_TOOL_ITERATIONS`：agent 工具调用循环最大迭代轮数（默认 3）
- `AGENT_MAX_TOTAL_TOOL_CALLS`：单次问答/解析累计工具调用上限（默认 10）
- `TOOL_RESULT_MAX_CHARS`：单条工具结果截断长度（默认 4000）
- `MCP_TOOL_SERVER_BASE_URL`：自托管 MCP 工具服务地址（compose 网络内 `http://mcp-server:8090`）
- `MCP_AUTH_TOKEN`：mcp-server 对 tools/list 与 tools/call 强制校验的 Bearer 令牌
- `MCP_SERVER_TOKEN_ENCRYPT_KEY`：后端加密存储用户填写的工具服务器令牌所用密钥
- `DUCKDUCKGO_MAX_RESULTS`：联网搜索单次返回结果上限（默认 5，范围 1–10）

## API

所有响应遵循统一信封：`{code, message, data, request_id}`。

### 认证
- `POST /api/v1/auth/register` — 注册
- `POST /api/v1/auth/login` — 登录（返回 access_token）
- `POST /api/v1/auth/refresh` — 轮换刷新令牌
- `POST /api/v1/auth/logout` — 退出
- `GET /api/v1/auth/me` — 当前用户

### 通知
- `POST /api/v1/notifications/ingest` — 来源导入（需 source + x-source-token 头）
- `GET /api/v1/notifications` — 个人通知列表
- `GET /api/v1/notifications/{id}` — 通知详情
- `POST /api/v1/notifications/{id}/confirm` — 确认生成待办（事务幂等）
- `POST /api/v1/notifications/{id}/discard` — 忽略
- `POST /api/v1/notifications/groups/{group_id}/publish` — 管理员发布组通知
- `GET /api/v1/notifications/groups/{group_id}` — 组通知列表
- `POST /api/v1/notifications/{id}/withdraw` — 撤回组通知
- `POST /api/v1/notifications/parse` — 流式解析预览（SSE，不入库，仅返回候选）

### 待办
- `GET /api/v1/todos` — 待办列表
- `POST /api/v1/todos/{id}/complete` — 完成
- `POST /api/v1/todos/{id}/restore` — 恢复
- `GET /api/v1/todos/{id}/breakdown` — 任务拆解建议
- `POST /api/v1/todos/{id}/breakdown/confirm` — 确认子任务

### 资料
- `POST /api/v1/attachments` — 上传（支持 group_id 表单字段）
- `GET /api/v1/attachments` — 列表（支持 group_id 查询）
- `GET /api/v1/attachments/{id}` — 详情
- `PUT /api/v1/attachments/{id}` — 编辑标题/正文（产生新版本）
- `DELETE /api/v1/attachments/{id}` — 删除
- `POST /api/v1/attachments/{id}/index` — 向量化索引

### 小组
- `POST /api/v1/groups` — 创建
- `GET /api/v1/groups` — 列表
- `GET /api/v1/groups/{id}` — 详情
- `POST /api/v1/groups/{id}/join` — 加入
- `POST /api/v1/groups/join-by-token` — 邀请令牌加入
- `POST /api/v1/groups/{id}/leave` — 退出
- `GET /api/v1/groups/{id}/members` — 成员列表
- `DELETE /api/v1/groups/{id}/members/{user_id}` — 移除成员
- `POST /api/v1/groups/{id}/regenerate-invite-token` — 重置邀请令牌
- `PUT /api/v1/groups/{id}/sync` — 设置个人同步开关

### 问答
- `POST /api/v1/qa/ask` — 提问（SSE 流式；事件 `tool`/`meta`/`data`/`done`，支持 `group_ids` 范围）

### 工具调用平台（MCP over HTTP）
- `POST /api/v1/tool-servers` — 登记工具服务器（令牌加密存储，列表不回传）
- `GET /api/v1/tool-servers` / `GET /api/v1/tool-servers/{id}` — 列表 / 详情（非所有者 404）
- `POST /api/v1/tool-servers/{id}/connect` — 执行 initialize + tools/list 握手并发现工具
- `GET /api/v1/tool-servers/{id}/tools` — 已发现工具清单
- `POST /api/v1/tool-servers/{id}/disconnect` — 断开并清空工具清单
- `PATCH /api/v1/tool-servers/{id}` / `DELETE /api/v1/tool-servers/{id}` — 更新 / 删除
- `POST /api/v1/skills` / `GET` / `PATCH` / `DELETE` — 技能配置；保存前校验引用格式、服务器归属与连接状态、工具是否存在（失败 BUSINESS_RULE 422）
- `GET /api/v1/tool-call-records` — 只读调用记录（按 owner 隔离，含 success/rejected/error 状态）

### 首页
- `GET /api/v1/home/checklist` — 今日/逾期/未来七天待办

### 提醒
- `POST /api/v1/reminders` — 创建提醒
- `GET /api/v1/reminders` — 待处理提醒列表
- `POST /api/v1/reminders/{id}/dismiss` — 忽略提醒

## 验证

后端单元/接口测试使用隔离的 SQLite 和每用例临时上传目录，不连接业务库或真实模型。迁移检查另外启动临时 PostgreSQL，需要 `embedded-postgres==18.6.3`（本地验证工具）以及其安装目录中的 pgvector 扩展；缺少本地依赖时明确失败。下列单条命令只代表各自范围；统一交付门禁见下节「统一交付门禁（delivery-gate）」。

```bash
# 后端测试
cd backend && .\.venv\Scripts\python -m pytest -q

# 迁移验证（embedded PostgreSQL）
cd backend && .\.venv\Scripts\python tests\test_migrations.py

# E2E 认证流程
cd backend && .\.venv\Scripts\python tests\e2e_auth_flow.py

# 前端构建
cd frontend && npm run build

# 前端时间语义及路由历史回归（Node 内置测试器，无额外测试依赖）
cd frontend && npm test

# 隔离浏览器验收（先构建frontend；另开终端运行，使用独立临时SQLite）
cd backend && .\.venv\Scripts\python -m tests.serve_date_acceptance
# 打开 http://localhost:5181，合成账号 acceptance / acceptance-only
# 合成上传文件路径由启动输出给出；首次文件提取和首次保存有意失败，修正/重试后验收。
# 该进程只绑定127.0.0.1，不连接业务数据库或真实模型；完成后Ctrl+C清理临时数据。

# Compose 配置校验
docker compose config --quiet

# 工具调用平台端到端（离线：本地 stub LLM + 真实 mcp-server 子进程 + 隔离 SQLite）
cd backend && .\.venv\Scripts\python.exe ..\apitest\run_all.py
# 报告输出到 apitest\report.html；全部通过退出 0，任一检查失败退出 1。
# 依赖 backend\.venv 已安装 requirements + requirements-dev（含 uvicorn / httpx / embedded_postgres）。
# 不连接业务库、不调用真实模型；仅使用 127.0.0.1 本地子进程，断网可重放。
```

## 统一交付门禁（delivery-gate）

本项目提供统一质量门禁，由根目录 `Makefile` 定义，并在 `.github/workflows/ci.yml` 中于 push 到 `main` 与 PR 时自动运行（可配置为 `main` 分支保护的 required check）。课程交付证据集中在 `reports/`（七类核查清单、审核记录、高风险三查、基准结果）。

```bash
# 测试 + 覆盖率门禁（≥60%）+ 前端测试；任一子步失败则整体退出非 0
make check
# 依赖漏洞扫描 + 密钥泄露扫描；任一失败则整体退出非 0
make check-security
# 列表接口性能基准（P95 ≤ 500ms）
make bench
```

退出码语义：`0` = 通过；非 `0` = 失败。`make check` 的覆盖率阈值由 `backend/pytest.ini` 的 `--cov-fail-under=60` 强制，未为过线调低；低于阈值即失败。

注意：
- Windows 本地：`make` 通常不在 PATH，改用 Git for Windows 自带的 `mingw32-make`（如 `mingw32-make check`）。
- 后端测试与基准依赖 `backend\.venv`：先 `cd backend && python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt`，或将 venv 加入 PATH。
- `make check-security` 的 `pip-audit` 首次运行需联网拉取漏洞库；之后可离线复跑。当前登记 2 条无修复版本且经评估不适用的例外（理由见 `reports/review-03.md`），通过 `Makefile` 的 `PIP_AUDIT_IGNORE` 忽略，未调低扫描等级。
- `make bench` 为进程内基准（不含 TCP/uvicorn 调度开销），P95 为保守下界；详见 `reports/bench.md`。

## Edge最小化与路由历史

前端固定vue-router 4.6.4，并回补[官方#2704](https://github.com/vuejs/router/pull/2704)：页面隐藏时不再写历史状态，离开页面时通过pagehide保留滚动位置。补丁脚本在npm安装、开发启动及构建前运行，遇到版本或源码变化会明确失败；升级路由时应重新审查并移除已由上游解决的回补。没有覆盖浏览器的history方法。

本地准备使用 `cd frontend && npm ci`；Docker构建也使用锁文件及同一补丁。验证用 `npm test`、`npm run build`。Docker开发环境若已启动，需 `docker compose up -d --no-deps --build web` 更新前端，然后刷新原项目标签。只重启旧容器不会更新其依赖。原生窗口仍需在实际Edge中验证最小化、任务栏恢复与草稿保留；无Vue的可启停开发复现为 `/src/edge-history-repro.html`，静态对照为 `/src/window-diagnostic.html`。记录见[窗口修复报告](docs/changes/fix-window-controls-and-date-aware-parsing/window-controls.md)。

## 解析请求时间与日期精度

每次文本、文件和通知解析向模型发送请求前，服务端都会注入 `request_sent_at`、`current_date`、`current_time`、`current_weekday`、`weekday_label` 和 `timezone`。网络重试发送前刷新，响应和相对日期换算使用对应发送尝试的快照。默认 `TIMEZONE=Asia/Shanghai`；`LLM_REQUEST_TIMEOUT=30`、`LLM_TOTAL_TIMEOUT=60`、`LLM_MAX_RETRIES=1` 集中限制调用。时间基准判定与相对日期换算不使用 MCP 工具或外部时间服务；MCP 工具（如联网搜索）仅补充非时间字段，不参与时间字段生成。

原文明确发布日期优先作为日期基准；没有时按发送日推算并标记待确认。周一至周日为同一自然周，本周已过日期不会自动推到下周。仅日期使用 `due_date`，精确时刻使用 UTC `due_at` 并按 `due_timezone` 显示，未知字段保持空，不补 09:00。确认写入的旧 `due_at`/`deadline` 字符串必须带时区偏移；新前端提交当地 `date`/`time` 由后端换算。

本次增加迁移 `0015_todo_time_precision`。实际业务库先备份，再从 `backend` 执行 `alembic upgrade head`，然后运行新版后端/前端；本变更的自动验证只操作临时测试库。旧版客户端不能完整展示仅日期记录。回退应用时保留新增列，结构降级若仍有仅日期记录会拒绝执行，不能以降级丢弃这些日期。

真实模型评测单独运行，使用合成通知并产生少量模型调用费用：

```powershell
# 在 backend 中执行，模型配置由指定文件/环境变量提供，勿将真实密钥提交到仓库
.\.venv\Scripts\python.exe -m tests.eval_parsing_time --env-file ../.env
```

报告默认为 `docs/changes/fix-window-controls-and-date-aware-parsing/model-evaluation.json`。无模型配置退出 2，评测失败退出 1，通过退出 0；报告不包含凭证或通知正文。真实评测不代替替身故障测试，尚未执行时不得声称模型效果已验证。

## 设计要点

- **授权**：服务端按当前身份与资源关系授权，默认拒绝（SEC-02）。
- **确认事务**：通知确认在单事务内创建待办，通过 `confirmation_key` 幂等去重（BE-14, AI-06）。
- **模型校验**：模型输出经 JSON Schema 校验，非法字段被剥离（AI-04）。
- **演示模式**：模型相关环境变量为空时使用本地替身，无外部调用。
- **向量索引**：资料切片后存入 pgvector，检索时按归属和组成员过滤。
