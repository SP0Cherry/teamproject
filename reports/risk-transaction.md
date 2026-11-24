# 高风险三查：事务（transaction）

## 风险
通知确认创建待办 + 标记通知已确认，若中途失败可能产生部分批次（待办已建但通知未标记，或反之），破坏原子性与幂等。

## 手段
复用 `backend/tests/test_confirmation.py` 的事务幂等用例：
- `test_confirm_is_idempotent`：同一通知连续确认两次，断言只产生一个批次（2 条），验证幂等。
- `test_confirm_candidate_without_title_rejected`：传入缺 title 的候选，断言返回 400 `PARAM_INVALID` 且**没有任何待办被创建**（无部分批次），验证校验失败时整体回滚。

## 查了什么
`ConfirmationService.confirm` 是否在单个事务内完成「校验 → 创建待办 → 标记通知已确认 → 提交」，校验失败时不落库。

## 判据
1. 重复确认同一通知只产生一个批次；
2. 候选校验失败时，`GET /api/v1/todos` 返回空（无部分写入）。

## 结果
两项用例均通过（在 `make check` 全量中 `160 passed`）。确认流程的 create+commit 位于同一 try 块，校验在写入前完成，`IntegrityError` 分支也会 rollback，保证原子性。

## 复跑命令
```bash
cd backend && python -m pytest tests/test_confirmation.py -q
```
