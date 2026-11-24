# 高风险三查：权限（authz）

## 风险
用户/组员越权访问不属于自己的小组或待办，导致数据泄露或篡改（水平越权）。

## 手段
复用既有授权测试：
- `backend/tests/test_authz.py`：`test_non_member_cannot_view_group`（非成员查看他人小组 → 403 `ACCESS_DENIED`）、`test_groups_list_only_returns_user_groups`（用户 B 列不出用户 A 的小组）。
- `backend/tests/test_confirmation.py`：`test_todo_owner_isolation`（用户 B 完成用户 A 的待办 → 404）。

## 查了什么
服务端是否按当前身份与资源归属授权：非成员看不到小组、列表只返回本人/本组资源、跨用户操作待办被拒绝。

## 判据
1. 非成员 `GET /api/v1/groups/{id}` 返回 403 `ACCESS_DENIED`；
2. 组员列表不包含未加入的小组；
3. 跨用户 `POST /api/v1/todos/{id}/complete` 返回 404（不泄露存在性）。

## 结果
三项用例均通过（在 `make check` 全量中 `160 passed`）。授权在服务端按归属判定，默认拒绝，个人与小组数据隔离。

## 复跑命令
```bash
cd backend && python -m pytest tests/test_authz.py tests/test_confirmation.py::test_todo_owner_isolation -q
```
