## Context

后端小组能力已完整实现（见 proposal），但前端仅有 `Groups.vue` 列表页，暴露创建/加入/列表三项。`GET /groups/{group_id}/members` 当前只返回 `[{ user_id, role }]`，不关联 `users` 表，前端无法识别成员身份。前端采用 Vue 3 + vue-router，API 调用统一走 `frontend/src/api/client.ts` 的 axios 实例与 `ApiEnvelope` 封装；受保护页面挂在 `WorkspaceLayout` 子路由下。后端分层为 api → service → repository，授权集中在 `AuthzService`。见 proposal.md - Why。

## Goals / Non-Goals

**Goals:**

- 把后端已有的组能力通过一个组详情页暴露给用户，使成员管理、同步、组通知、组资料可实际操作。
- 用最小的后端契约补全（成员列表关联 users）让成员界面可用，不新增表、不迁移。
- 保持服务端授权为真相，前端仅做条件渲染，不引入新的授权路径。

**Non-Goals:**

- 不实现转让所有权、解散组、编辑组信息、角色升降、组通知修订、邀请令牌过期（后续批次）。
- 不改组通知发布链路（服务端即时解析发布），不新增发布前预览确认步骤。
- 不重构现有列表页之外的个人流程页面。

## Decisions

### 1. 单页组详情，内部分区，而非多子路由

组详情路由 `/groups/:id` 单页内分区：组信息、成员、同步、组通知、组资料。移动端纵向单列滚动，桌面端可两列。

- 理由：近期交付节点要求快速可用；单页减少路由与状态管理复杂度，五个区共用同一份组上下文（group_id、myRole）。
- 备选：每个功能独立子路由（`/groups/:id/members` 等）——结构更清晰但工作量与导航成本更高，本变更不采用，留待组功能深化时再拆。

### 2. 前端 API 封装复用现有模式

新增 `frontend/src/api/groups.ts`、`frontend/src/api/attachments.ts`，在 `notifications.ts` 中补组发布/列表/撤回方法，均复用 `client.ts` 的 `api` 实例与 `ApiEnvelope`。不在组件内裸写 axios。

### 3. 成员列表后端关联 users（非破坏性契约补全）

`GroupRepository.list_members` 改为 `join(User, User.id == GroupMember.user_id)`，返回带 `username` 的行；`GET /groups/{group_id}/members` 序列化新增 `username`、`joined_at`（取 `GroupMember.created_at`）。仅新增字段，旧调用方忽略多余字段不受影响。无数据库迁移。

- 备选：前端拿到 `user_id` 后逐个查用户 —— N+1 且暴露用户查询接口，不可取。

### 4. 授权：前端条件渲染 + 服务端二次校验

进入组详情先 `GET /groups/{group_id}`（校验成员身份，返回邀请令牌以及当前用户的 `my_role` 与 `my_sync_enabled`），再并行拉成员/通知/资料。`my_role` 用于条件渲染管理入口（重置令牌、移除成员、发布/撤回通知仅 admin/owner 可见），`my_sync_enabled` 作为同步开关初始值。成员列表不返回其他成员的同步设置，避免越权暴露（SEC-04）。所有写操作仍由后端 `AuthzService` 校验，前端不缓存权限、不绕过校验（SEC-02、SEC-03）。

### 5. 组通知发布与展示

发布调 `POST /notifications/groups/{group_id}/publish`（body `{ text }`），服务端解析并发布、向同步成员投递副本。前端展示响应中的 `candidates` 作为发布结果（只读），不阻断发布；发布成功后刷新组通知列表。撤回调 `POST /notifications/{id}/withdraw`，仅 admin 可用。

### 6. 视图状态与错误反馈

每个分区独立维护 loading / empty / error 状态（PROD-03）；写操作失败就近提示并保留输入，不静默失败。owner 点击退出时入口置灰并提示「需先转让所有权」（转让未实现，避免触发后端死锁报错）。

### 7. 组列表聚合展示

`GET /groups` 扩展返回 `description`、`my_role`、`my_sync_enabled`、`member_count`，使列表卡片可展示关键信息并直接进入详情，无需逐组发起详情请求。`member_count` 用关联子查询聚合，`my_role` / `my_sync_enabled` 取当前用户的 membership（`list_for_user` 已 join `GroupMember`）。仅新增字段，非破坏性。

## Risks / Trade-offs

- **owner 无法退组的死锁仍在** → 前端明确提示并标注为后续 `transfer-ownership` 批次；不掩盖限制。
- **组通知发布无预览确认（PROD-10 合规待评估）** → 本变更不改发布链路，记录为已知限制，后续批次评估是否加「解析预览→确认发布」。
- **单页信息密度高** → 分区卡片化 + 移动端单列；组通知与组资料区默认折叠或分页，避免首屏过载。
- **成员列表 join 增加查询开销** → 课程项目组规模小，可接受；`group_members(group_id, user_id)` 已有索引，join 走主键，性能无忧。

## Migration Plan

无数据库迁移。部署顺序：后端先上线（成员列表新增字段为非破坏性），前端构建产物随后替换；二者可独立回滚。回滚前端即可恢复旧列表页行为，后端多余字段不影响旧前端。
