# 时间契约验证

规则：BE-03/04/05/15、SEC-02/11、PROD-05/10/13、TEST-03/05/08。

命令（backend）：`.\.venv\Scripts\python.exe -m pytest -q --tb=line`。最新实际结果106 passed in 15.30s、退出码0；包含后续新增的2条完整年月日基准提示回归。

`tests/test_date_context.py::test_parse_save_reload_and_invalid_batch` 使用隔离SQLite和ASGI客户端登录：解析后待办列表仍为空；确认上海2026-11-11 15:00返回07:00Z；仅日期保存独立due_date且due_at为空；仅时间明确接受无截止日期后时刻保留在说明；逐条GET重读值与保存响应一致。混入2026-02-30的批次返回HTTP400/PARAM_INVALID且列表仍为原3条，未产生半批写入。

`test_invalid_confirmation_is_rejected` 拒绝无偏移due_at、矛盾date/due_date、due_date与due_at同时存在、多余owner_id及未经接受的仅时间输入。现有确认及认证回归的归属隔离、重复确认仍随全量测试通过；本证据不扩展为未测并发安全声明。

`test_date_only_overdue_boundary` 固定业务时钟验证11-11上海23:59:59仍是今日任务、次日00:00转逾期。`test_precise_and_unknown_tasks_keep_home_and_reminder_semantics` 验证UTC11-10 16:30归上海11-11今日；未知时间仍出现在清单且不制造提醒；既有精确提醒重复处理只发送一次。日程真实浏览器重读证据见[ui-time.md](ui-time.md)。

真实PostgreSQL字段互斥约束及旧时刻数值不变由[migration.md](migration.md)中的隔离迁移检查验证，不能用SQLite接口测试替代。完整浏览器文件/通知替身主流程仍未完成，见[integration.md](integration.md)。
