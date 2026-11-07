# 数据字典

本字典描述业务库表与字段的含义、类型、空值、默认值、枚举、归属、约束、索引及敏感等级（DATA-01 至 DATA-06）。结构或语义变更须同步更新。向量元数据与跨存储关联标识随对应能力登记。

## 命名约定

- 表名：小写复数；字段名：小写单数 snake_case。
- 关联标识：`<资源单数>_id`；时间戳：`_at`（UTC，带时区）；仅日期：`_date`。
- 精确时刻统一以 UTC 存储；仅日期使用独立日期字段，不换算为 UTC 时刻；未知时间为 NULL。
- 审计字段：`created_at`、`updated_at`、`created_by` 由服务端赋值。

## 敏感等级

| 等级 | 说明 | 处理 |
| --- | --- | --- |
| 公开 | 无个人信息 | 可正常返回 |
| 内部 | 业务元数据 | 仅向有权用户返回 |
| 敏感 | 密码摘要、令牌、模型凭证 | 永不返回，不入日志 |
| 个人信息 | 可识别个人的资料正文、联系方式 | 按归属与成员关系授权返回，日志脱敏 |

## 留存清单（DATA-07）

| 对象 | 保留期 | 起算点 | 清理方式 |
| --- | --- | --- | --- |
| background_tasks | 90 天 | updated_at | 后台清理已完成/失败超过 90 天的记录 |
| 原文件附件 | 随所属资料 | 资料删除 | 删除先失效访问再异步清理 |
| 提取文本/切片 | 随所属资料版本 | 版本失效 | 索引重建时清理旧版本 |
| 审计日志 | 180 天 | created_at | 受控清理，另记操作 |

## 表：background_tasks

后台任务状态与结果记录（BE-13）。归属为发起用户 `owner_id`。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 任务唯一标识 | 内部 |
| task_type | VARCHAR(64) | 否 | - | 任务类型，如 ocr、index、sync | 内部 |
| status | task_status 枚举 | 否 | pending | pending/running/succeeded/failed | 内部 |
| owner_id | VARCHAR(36) | 否 | - | 发起用户，归属字段 | 内部 |
| progress | INTEGER | 否 | 0 | 0-100 进度 | 内部 |
| error | TEXT | 是 | NULL | 失败错误摘要，不含堆栈或机密 | 内部 |
| result | TEXT | 是 | NULL | 结果摘要，脱敏后存储 | 内部 |
| attempts | INTEGER | 否 | 0 | 尝试次数 | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_background_tasks_task_type`、`ix_background_tasks_status`、`ix_background_tasks_owner_id`。

**归属与授权**：`owner_id` 标记任务归属；查询时按当前用户过滤，无权访问按不存在处理（SEC-02）。

**状态流转**：pending → running → succeeded/failed；失败可重试，重试递增 attempts。

## 表：users

用户账号。`password_hash` 为 Argon2id 摘要（SEC-05），永不返回。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 用户唯一标识 | 内部 |
| username | VARCHAR(64) | 否 | - | 登录名，唯一 | 个人信息 |
| password_hash | VARCHAR(255) | 否 | - | Argon2id 密码摘要 | 敏感 |
| is_active | BOOLEAN | 否 | true | 账号是否启用 | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_users_username`（唯一）。

## 表：sessions

服务端会话，保存刷新令牌摘要以支持立即撤销（SEC-05、SEC-06）。归属为 `user_id`。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 会话标识 | 内部 |
| user_id | VARCHAR(36) | 否 | - | 所属用户，外键 users.id | 内部 |
| refresh_token_hash | VARCHAR(255) | 否 | - | 刷新令牌 SHA-256 摘要 | 敏感 |
| is_revoked | BOOLEAN | 否 | false | 是否已撤销 | 内部 |
| expires_at | TIMESTAMPTZ | 否 | - | 过期时间（UTC） | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_sessions_user_id`。

**状态流转**：刷新时撤销旧会话并签发新会话（轮换）；退出时撤销当前会话。

## 表：groups

小组。`owner_id` 为创建者，自动成为 owner 成员。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 小组唯一标识 | 内部 |
| name | VARCHAR(128) | 否 | - | 小组名称 | 内部 |
| description | VARCHAR(512) | 是 | NULL | 小组描述 | 内部 |
| owner_id | VARCHAR(36) | 否 | - | 创建者用户 id | 内部 |
| invite_token | VARCHAR(64) | 否 | 随机 | 加入邀请令牌，管理员可重置 | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_groups_owner_id`、`ix_groups_invite_token`（唯一）。

## 表：group_members

小组成员关系。`(group_id, user_id)` 唯一。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 关系标识 | 内部 |
| group_id | VARCHAR(36) | 否 | - | 所属小组 | 内部 |
| user_id | VARCHAR(36) | 否 | - | 成员用户 | 内部 |
| role | group_role 枚举 | 否 | member | owner/admin/member | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 加入时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_group_members_group_id`、`ix_group_members_user_id`；唯一约束 `uq_group_member(group_id, user_id)`。

**授权规则**：组资源仅成员可访问；owner/admin 可管理成员。非成员访问按 ACCESS_DENIED 处理（SEC-03）。

## 表：attachments

通知附件，含提取状态。文件存储在私有卷 `storage_path`，不直接对外暴露（SEC-08）。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 附件标识 | 内部 |
| owner_id | VARCHAR(36) | 否 | - | 上传者，归属字段 | 内部 |
| group_id | VARCHAR(36) | 是 | NULL | 所属小组，可为空（个人附件） | 内部 |
| filename | VARCHAR(255) | 否 | - | 原始文件名 | 内部 |
| mime_type | VARCHAR(128) | 否 | - | MIME 类型 | 内部 |
| file_size | BIGINT | 否 | - | 字节数 | 内部 |
| storage_path | VARCHAR(512) | 否 | - | 私有存储路径 | 内部 |
| status | attachment_status 枚举 | 否 | pending | pending/processing/succeeded/failed | 内部 |
| extracted_text | TEXT | 是 | NULL | 提取文本 | 个人信息 |
| error | VARCHAR(512) | 是 | NULL | 失败原因摘要 | 内部 |
| task_id | VARCHAR(36) | 是 | NULL | 关联后台任务 | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 上传时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_attachments_owner_id`、`ix_attachments_group_id`、`ix_attachments_status`。

**限额**：单文件 ≤ `MAX_UPLOAD_MB`；PDF ≤ `MAX_PDF_PAGES` 页；图片像素 ≤ `MAX_IMAGE_PIXELS`；文本 ≤ `MAX_TEXT_CHARS` 字符。

**状态流转**：pending → processing → succeeded/failed。OCR 无文本或仅空白时标记 failed。

## 表：notifications

通知记录。`parsed` 为模型抽取的 JSON 候选结果，须经人工确认后才生成待办（AI-06）。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 通知标识 | 内部 |
| owner_id | VARCHAR(36) | 否 | - | 接收用户，归属字段 | 内部 |
| group_id | VARCHAR(36) | 是 | NULL | 来源小组，可为空 | 内部 |
| source | VARCHAR(64) | 否 | - | 来源标识（需共享密钥鉴权） | 内部 |
| raw_text | TEXT | 否 | - | 通知原文 | 个人信息 |
| parsed | TEXT | 是 | NULL | 抽取候选 JSON | 个人信息 |
| status | notification_status 枚举 | 否 | pending | pending/confirmed/discarded | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_notifications_owner_id`、`ix_notifications_group_id`、`ix_notifications_status`。

## 表：todos

个人待办。由通知确认生成（`source_notification_id`、`confirmation_key`）或手动创建。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 待办标识 | 内部 |
| owner_id | VARCHAR(36) | 否 | - | 归属用户 | 内部 |
| group_id | VARCHAR(36) | 是 | NULL | 所属小组 | 内部 |
| title | VARCHAR(255) | 否 | - | 事件名称 | 内部 |
| description | TEXT | 是 | NULL | 注意事项 | 内部 |
| location | VARCHAR(512) | 是 | NULL | 地点 | 内部 |
| due_at | TIMESTAMPTZ | 是 | NULL | 截止时间（UTC）；仅日期存当日 00:00 UTC | 内部 |
| status | todo_status 枚举 | 否 | pending | pending/done | 内部 |
| source_notification_id | VARCHAR(36) | 是 | NULL | 来源通知 | 内部 |
| confirmation_key | VARCHAR(64) | 是 | NULL | 确认批次幂等键 | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_todos_owner_id`、`ix_todos_group_id`、`ix_todos_status`、`ix_todos_due_at`、`ix_todos_confirmation_key`。

**幂等**：同一通知的重复确认通过 `confirmation_key` 去重，最多产生一批待办（BE-14）。

## 表：resource_chunks

资料切片与向量索引。每个附件版本的文本被切片后生成向量，用于 RAG 检索（AI-03）。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 切片标识 | 内部 |
| attachment_id | VARCHAR(36) | 否 | - | 所属附件 | 内部 |
| version | INT | 否 | 1 | 附件版本号 | 内部 |
| chunk_index | INT | 否 | - | 切片序号 | 内部 |
| content | TEXT | 否 | - | 切片文本 | 内部 |
| embedding | vector(1536) | 是 | NULL | 向量嵌入 | 内部 |
| owner_id | VARCHAR(36) | 否 | - | 归属用户（授权冗余） | 内部 |
| group_id | VARCHAR(36) | 是 | NULL | 所属小组（授权冗余） | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_resource_chunks_attachment_id`、`ix_resource_chunks_owner_id`、`ix_resource_chunks_group_id`，唯一约束 `(attachment_id, version, chunk_index)`。

**版本清理**：附件编辑产生新版本后，旧版本切片立即删除（DATA-02）。

## 表：reminders

站内提醒。后台按 `remind_at` 调度，状态机 pending → sent/dismissed。

| 字段 | 类型 | 空值 | 默认 | 说明 | 敏感等级 |
| --- | --- | --- | --- | --- | --- |
| id | VARCHAR(36) | 否 | uuid | 提醒标识 | 内部 |
| user_id | VARCHAR(36) | 否 | - | 归属用户 | 内部 |
| todo_id | VARCHAR(36) | 是 | NULL | 关联待办 | 内部 |
| title | VARCHAR(255) | 否 | - | 提醒标题 | 内部 |
| remind_at | TIMESTAMPTZ | 否 | - | 提醒时间（UTC） | 内部 |
| status | reminder_status 枚举 | 否 | pending | pending/sent/dismissed | 内部 |
| message | TEXT | 是 | NULL | 提醒内容 | 内部 |
| created_at | TIMESTAMPTZ | 否 | now() | 创建时间（UTC） | 内部 |
| updated_at | TIMESTAMPTZ | 否 | now() | 更新时间（UTC） | 内部 |

**索引**：`ix_reminders_user_id`、`ix_reminders_status`、`ix_reminders_remind_at`。

## 扩展：vector

PostgreSQL pgvector 扩展，用于向量检索。向量元数据（文件标识、归属、内容/索引版本、切片序号）随资料索引能力登记，向量副本不作为授权真相（DATA-02）。
