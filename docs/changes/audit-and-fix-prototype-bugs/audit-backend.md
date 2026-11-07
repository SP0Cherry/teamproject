# 后端规范合规审计

审计范围：BE-01 至 BE-16
审计日期：2026-11-07

## 审计结果

| 规范项 | 判定 | 证据 |
| :--- | :--- | :--- |
| BE-01 分层与依赖方向 | 符合 | api→services→repositories 三层分离；repositories 内含 SQL/ORM，services 不含 SQL |
| BE-02 接口命名与版本控制 | 符合 | `/api/v1` 前缀，资源小写复数；GET 读取、POST 创建、DELETE 删除 |
| BE-03 请求与响应结构 | 符合 | 统一信封 `{code, message, data, request_id}`（`response.py`）；ApiError 携带 HTTP 状态 |
| BE-04 错误码体系 | 符合 | ErrorCode 常量与 HTTP 状态映射完整（`response.py`）；PARAM/AUTH/ACCESS/CONFLICT/BUSINESS/DEPENDENCY 全覆盖 |
| BE-05 参数校验的位置 | 符合 | Pydantic 模型在接口层校验（如 `ParseTextRequest` `Field(min_length=1)`） |
| BE-06 数据访问与事务 | 部分符合 | repositories 层操作 DB；需核查通知确认整批入库的原子事务 |
| BE-07 事务内的禁止项 | 部分符合 | 需核查事务内是否有外部 HTTP/模型调用；组通知同步可能在事务外 |
| BE-08 幂等与并发 | 符合 | Todo 有 `confirmation_key` 幂等键；编辑使用版本条件更新 |
| BE-09 分页、排序与筛选 | 不符合 | 列表接口（`GET /todos`、`GET /notifications`）未实现 page/page_size/sort 参数 |
| BE-10 排序的唯一兜底键 | 不适用 | 无分页即无排序兜底需求 |
| BE-11 非法筛选的失败策略 | 不适用 | 无筛选参数 |
| BE-12 配置外置 | 符合 | 环境变量注入（`config.py`）；`.env.example` 存在且无真实密钥 |
| BE-13 文件处理与异步任务 | 部分符合 | 文件上传校验 MIME 类型与大小；解析为同步调用，未走后台任务 |
| BE-14 数据权限与 AI 检索 | 符合 | `get_current_user` 依赖注入；向量检索按归属过滤 |
| BE-15 时间与提醒一致性 | 部分符合 | `due_at` 使用 `DateTime(timezone=True)`；需核查提醒去重与版本 |
| BE-16 日志、审计与验证 | 部分符合 | `logging.py` 使用 structlog；需核查是否记录 request_id 且不记录敏感信息 |

## 缺口清单

1. **BE-09**：列表接口缺少分页参数 —— 后续变更（涉及所有列表接口）
2. **BE-13**：文件解析未异步化 —— 后续变更
3. **BE-16**：需确认日志含 request_id 且无敏感信息 —— 本次修复（核查 logging.py）
