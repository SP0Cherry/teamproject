## 1. 后端成员列表契约补全

- [x] 1.1 `GroupRepository.list_members` 关联 `users` 表返回 `username`，验证：新增/更新单测断言返回结构含 `username`，非成员不出现
- [x] 1.2 `GET /groups/{group_id}/members` 序列化新增 `username`、`joined_at`（取 `GroupMember.created_at`），验证：pytest 断言响应字段含 `username`/`joined_at`，非成员请求返回拒绝且不泄露内容
- [x] 1.3 回归现有组相关测试不受影响，验证：`pytest backend/tests -k group` 全部通过
- [x] 1.4 实现揭示的必要扩展：`GET /groups/{group_id}` 返回当前用户的 `my_role` 与 `my_sync_enabled`（供详情页角色渲染与同步开关初始值，非破坏性新增字段，不泄露他人设置），已同步更新 design 决策 4，验证：pytest 组测试通过
- [x] 1.5 实现揭示的必要扩展：`GET /groups` 聚合返回 `description`、`my_role`、`my_sync_enabled`、`member_count`（`list_for_user` 关联子查询聚合成员数），供列表卡片展示，已同步更新 design 决策 7，验证：pytest 组测试通过

## 2. 前端 API 封装与路由

- [x] 2.1 新增 `frontend/src/api/groups.ts`，封装 list/get/create/join/joinByToken/leave/members/removeMember/regenerateToken/setSync，复用 `client.ts` 的 `api` 实例与 `ApiEnvelope`，验证：`npx vue-tsc --noEmit` 编译通过
- [x] 2.2 新增 `frontend/src/api/attachments.ts`，封装 upload（multipart，带 `group_id`）、list（按 `group_id` 过滤）、get、delete，验证：`npx vue-tsc --noEmit` 编译通过
- [x] 2.3 在 `frontend/src/api/notifications.ts` 补 `publishGroup`/`listGroup`/`withdraw` 方法，验证：`npx vue-tsc --noEmit` 编译通过
- [x] 2.4 路由新增 `/groups/:id` 子路由（`WorkspaceLayout` 下，指向 `GroupDetail` 视图），沿用登录守卫，验证：未登录访问跳转登录并带 redirect，登录后回到该详情页；刷新深链接可回到同一页面

## 3. 组详情页骨架与组信息区

- [x] 3.1 新建 `GroupDetail.vue` 骨架：按 `group_id` 拉取组信息，分区容器（信息/成员/同步/通知/资料），每区独立 loading/empty/error 状态（PROD-03），验证：进入详情页显示组名与描述，加载中与失败状态可见且失败可重试
- [x] 3.2 信息区展示邀请令牌 + 复制按钮；admin/owner 显示「重置令牌」按钮并接 `regenerate-invite-token`，成功后刷新令牌展示，验证：复制到剪贴板可用，admin 重置后令牌更新
- [x] 3.3 信息区「退出组」按钮：非 owner 接 `leave` 成功后跳回组列表；owner 按钮置灰并提示「需先转让所有权」，验证：非 owner 退出成功，owner 看到提示且不触发请求

## 4. 成员区

- [x] 4.1 成员列表展示 `username`/`role`/`joined_at`，当前用户的 `my_role` 由 `GET /groups/{id}` 返回（design 决策 4），验证：列表显示可识别的用户名与角色，而非裸 UUID
- [x] 4.2 admin/owner 的「移除成员」按钮（不能移除自己和 owner）接 `DELETE /groups/{id}/members/{uid}`，成功后刷新列表，验证：移除生效；尝试移除自己或 owner 时入口不可用或被后端拒绝

## 5. 同步区

- [x] 5.1 「同步组通知到我的待办」开关接 `PUT /groups/{id}/sync`，初始值取 `GET /groups/{id}` 的 `my_sync_enabled`，切换后乐观更新并回读确认，验证：切换后状态持久，刷新页面保持新状态；关闭后已有待办不消失

## 6. 组通知区

- [x] 6.1 发布文本框 + 发布按钮接 `POST /notifications/groups/{id}/publish`，展示返回的 `candidates`（只读）与成功提示，发布后刷新组通知列表，验证：admin 发布成功，列表出现新通知；非 admin 无发布入口
- [x] 6.2 组通知列表展示 `raw_text` 摘要/`status`/`published`；admin/owner 的「撤回」按钮接 `POST /notifications/{id}/withdraw`，验证：撤回后 `published` 变为 false，非 admin 无撤回入口

## 7. 组资料区

- [x] 7.1 上传入口（multipart/form-data，带 `group_id`）接 `POST /attachments`，展示处理中状态，成功后刷新资料列表，验证：上传成功后列表出现本组新资料
- [x] 7.2 组资料列表接 `GET /attachments?group_id=`，展示文件名/状态；删除按钮接 `DELETE /attachments/{id}`（仅 admin/owner 可见，与后端授权一致），验证：列表仅含本组资料，删除生效且不影响他组

## 8. 组列表页增强

- [x] 8.1 列表卡片展示组描述、成员数、我的角色、同步状态；卡片可点击进入对应详情页，验证：信息正确显示，点击跳转到 `/groups/:id`
- [x] 8.2 列表页保留创建/加入，操作成功后刷新列表并给出反馈，验证：创建/加入后列表即时更新

## 9. 测试与回归

- [x] 9.1 后端成员列表契约测试（新字段 + 非成员拒绝）与列表/详情聚合字段测试，验证：新增 `tests/test_group_contract.py` 4 项通过，`pytest backend/tests`（排除环境问题文件）全量 145 passed
- [x] 9.2 前端路由与详情页关键路径测试（进入详情、退出组、同步切换），验证：新增 `frontend/tests/group-routes.test.mjs` 3 项，`npm test` 全量 14 passed；`vue-tsc --noEmit` 类型检查通过
- [x] 9.3 全量回归通过，验证：后端 pytest 145 passed、apitest 46 passed、前端 npm test 14 passed、前端 `npm run build`（vue-tsc + vite）成功、`scripts/check_secrets.py` OK。说明：当前 Windows 环境无 `make`，且 `pytest.ini` 依赖 `pytest-cov`、`test_migrations.py` 依赖 `embedded_postgres`（均为既有环境缺口，非本次引入），故以等价命令逐项验证，全部通过

## 10. 文档同步

- [x] 10.1 README 页面清单补齐组详情页入口及能力（PROD-02、PROD-14），验证：页面清单含 `/groups/:id` 路由与对应能力说明
