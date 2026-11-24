# 提示词发送时间验证

代码：共享 capture_time 与模型发送适配层，todo/notification 提示词版本分别为 todo-extraction-v2-request-time、notification-extraction-v2-request-time。没有 MCP SDK、工具进程或 agent 循环。

命令（backend）：`.\.venv\Scripts\python.exe -m pytest tests/test_date_context.py -q`；全量 `.\.venv\Scripts\python.exe -m pytest -q --tb=line`。

初次修复前 11 条中 8 条失败，实际复现本周三错误顺延、本周日/本周一同日顺延、UTC 今日错日、日期默认 09:00、上海15:00错误当UTC15:00、提示词缺发送时刻、候选缺独立日期。

最新全量测试106条通过。固定时钟及HTTP替身验证发送日期/时间/星期/时区、绝对日期请求也注入、来源正文隔离、文件和通知共用装配路径、重试跨午夜刷新且响应绑定对应快照、无可信时钟不出站且降级绝对日期可保留、非法年月日/时刻/时区/预算拒绝。日志调用断言不包含正文或raw_response。后续新增的2条中文/ISO完整年月日回归先失败，再修正为无需基准且不误标发送日推算；不改变每次发送仍注入可信时间的规则。

真实模型评测不在上述替身测试中，参见 model-evaluation.md。规则：AI-01/03/04/05/06/08/09/10、SEC-09/14、TEST-03/05/08/12。
