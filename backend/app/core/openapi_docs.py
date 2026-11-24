"""Shared OpenAPI documentation helpers (Task 8).

Provides reusable error-response schemas so every route documents the same
error envelope shape and HTTP status -> business code mapping declared in
``app.core.response``.
"""

from typing import Any

from pydantic import BaseModel


class ErrorPayload(BaseModel):
    code: str
    message: str
    data: Any | None = None
    request_id: str | None = None


class Envelope(BaseModel):
    code: str = "OK"
    message: str = "ok"
    data: Any | None = None
    request_id: str | None = None


_ERRORS = {
    400: ("PARAM_INVALID", "参数校验失败"),
    401: ("AUTH_INVALID", "未登录或令牌无效"),
    403: ("ACCESS_DENIED", "无访问权限"),
    404: ("RESOURCE_NOT_FOUND", "资源不存在或非所有者（与不存在不可区分）"),
    409: ("CONFLICT_VERSION / CONFLICT_STATE", "版本或状态冲突"),
    422: ("BUSINESS_RULE", "业务规则校验失败（如工具引用无效、服务器未连接）"),
    503: ("DEPENDENCY_UNAVAILABLE", "外部依赖（模型/工具服务）不可用"),
}


def err(status: int) -> dict:
    code, desc = _ERRORS.get(status, ("INTERNAL_ERROR", "服务器内部错误"))
    return {"model": ErrorPayload, "description": f"{code}：{desc}"}


def responses(*statuses: int) -> dict:
    """Build a ``responses=`` mapping for the given HTTP status codes."""
    return {s: err(s) for s in statuses if s in _ERRORS}


LOGIN_REQUIRED = "需要登录：请求头携带 `Authorization: Bearer <令牌>`。"
