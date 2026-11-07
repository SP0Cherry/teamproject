"""Unified API response envelope and error codes (BE-03, BE-04)."""

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode:
    PARAM_INVALID = "PARAM_INVALID"
    PARAM_MISSING = "PARAM_MISSING"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_REVOKED = "AUTH_REVOKED"
    ACCESS_DENIED = "ACCESS_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT_VERSION = "CONFLICT_VERSION"
    CONFLICT_STATE = "CONFLICT_STATE"
    BUSINESS_RULE = "BUSINESS_RULE"
    BUSINESS_IDEMPOTENT = "BUSINESS_IDEMPOTENT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    DEPENDENCY_TIMEOUT = "DEPENDENCY_TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_HTTP_STATUS = {
    ErrorCode.PARAM_INVALID: 400,
    ErrorCode.PARAM_MISSING: 400,
    ErrorCode.AUTH_INVALID: 401,
    ErrorCode.AUTH_EXPIRED: 401,
    ErrorCode.AUTH_REVOKED: 401,
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.CONFLICT_VERSION: 409,
    ErrorCode.CONFLICT_STATE: 409,
    ErrorCode.BUSINESS_RULE: 422,
    ErrorCode.BUSINESS_IDEMPOTENT: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.DEPENDENCY_UNAVAILABLE: 503,
    ErrorCode.DEPENDENCY_TIMEOUT: 504,
    ErrorCode.INTERNAL_ERROR: 500,
}


def http_status_for(code: str) -> int:
    return _HTTP_STATUS.get(code, 500)


class ApiResponse(BaseModel):
    code: str = "OK"
    message: str = "ok"
    data: Any | None = None
    request_id: str | None = None


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        data: Any | None = None,
        status: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.data = data
        self.status = status if status is not None else http_status_for(code)


def error_response(
    code: str,
    message: str,
    request_id: str,
    data: Any | None = None,
    status: int | None = None,
) -> JSONResponse:
    status = status if status is not None else http_status_for(code)
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "message": message,
            "data": data,
            "request_id": request_id,
        },
    )


def success_response(
    data: Any = None,
    message: str = "ok",
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": "OK",
        "message": message,
        "data": data,
        "request_id": request_id,
    }
