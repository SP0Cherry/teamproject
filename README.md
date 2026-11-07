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
| 小组 | `/groups` | 创建/加入/退出、成员管理、同步开关、发布通知 |
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
- `POST /api/v1/qa/ask` — 提问（支持 group_ids 范围）

### 首页
- `GET /api/v1/home/checklist` — 今日/逾期/未来七天待办

### 提醒
- `POST /api/v1/reminders` — 创建提醒
- `GET /api/v1/reminders` — 待处理提醒列表
- `POST /api/v1/reminders/{id}/dismiss` — 忽略提醒

## 验证

```bash
# 后端测试
cd backend && .\.venv\Scripts\python -m pytest -q

# 迁移验证（embedded PostgreSQL）
cd backend && .\.venv\Scripts\python tests\test_migrations.py

# E2E 认证流程
cd backend && .\.venv\Scripts\python tests\e2e_auth_flow.py

# 前端构建
cd frontend && npm run build

# Compose 配置校验
docker compose config --quiet
```

## 设计要点

- **授权**：服务端按当前身份与资源关系授权，默认拒绝（SEC-02）。
- **确认事务**：通知确认在单事务内创建待办，通过 `confirmation_key` 幂等去重（BE-14, AI-06）。
- **模型校验**：模型输出经 JSON Schema 校验，非法字段被剥离（AI-04）。
- **演示模式**：模型相关环境变量为空时使用本地替身，无外部调用。
- **向量索引**：资料切片后存入 pgvector，检索时按归属和组成员过滤。
