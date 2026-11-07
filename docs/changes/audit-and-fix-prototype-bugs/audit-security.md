# 安全规范合规审计

审计范围：SEC-01 至 SEC-18
审计日期：2026-11-07

## 审计结果

| 规范项 | 判定 | 证据 |
| :--- | :--- | :--- |
| SEC-01 默认拒绝 | 符合 | `router.beforeEach` 未登录跳转登录页；后端 `get_current_user` 依赖 |
| SEC-02 逐资源授权判定 | 符合 | TodoService.get/get 校验 `current_user.id`；组资源校验成员关系 |
| SEC-03 附件与文件读取 | 部分符合 | 文件存储标识服务端生成；需核查下载/预览是否每次校验权限 |
| SEC-04 越权失败场景 | 部分符合 | 有 `test_authz.py`；需核查组外访问、退出后读取等场景 |
| SEC-05 认证与会话 | 符合 | Argon2id 密码哈希（`security.py`）；JWT access token + refresh token |
| SEC-06 令牌存放与轮换 | 部分符合 | refresh token 存服务端哈希；需核查 Cookie 属性（HttpOnly/Secure/SameSite） |
| SEC-07 CSRF 与跨域 | 部分符合 | 需核查 CORS 配置与 Origin 校验 |
| SEC-08 密钥与机密 | 符合 | 环境变量注入；`.env.example` 无真实密钥；`.gitignore` 排除 .env |
| SEC-09 外部内容不可信 | 符合 | 模型输出经 schema 校验（`model.py validate_output`）；不直接写正式待办 |
| SEC-10 出站地址白名单 | 部分符合 | LLM base_url 由配置决定；需核查是否限制用户传入 URL |
| SEC-11 输入校验与批量赋值 | 符合 | Pydantic 模型白名单字段；owner_id 由服务端赋值 |
| SEC-12 输出转义与注入防护 | 部分符合 | SQLAlchemy 参数化查询；需核查前端 XSS 防护与 AI 回答净化 |
| SEC-13 文件解析隔离 | 部分符合 | 临时文件使用 NamedTemporaryFile；需核查解压炸弹与超时限制 |
| SEC-14 敏感数据与 AI 数据边界 | 部分符合 | 需核查日志不包含文件正文与模型提示 |
| SEC-15 滥用防护与资源配额 | 不符合 | 未实现速率限制（无 429 响应）；上传/AI 调用无限流 |
| SEC-16 依赖引入与许可证 | 部分符合 | `requirements.txt` 存在；需核查许可证白名单 |
| SEC-17 依赖漏洞扫描 | 不符合 | 无漏洞扫描配置 |
| SEC-18 删除、撤权与安全审计 | 部分符合 | 文件删除清理存储；需核查安全审计日志 |

## 缺口清单

1. **SEC-15**：缺少速率限制与资源配额 —— 后续变更（需引入限流中间件）
2. **SEC-17**：缺少依赖漏洞扫描 —— 后续变更
3. **SEC-06/07**：需核查 Cookie 属性与 CORS 配置 —— 本次修复（核查 main.py）
4. **SEC-14**：需核查日志脱敏 —— 本次修复（核查 logging.py）
