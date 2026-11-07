"""Helpers for async task responses (BE-03, BE-13)."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.response import success_response


def accepted_response(
    task_id: str,
    request: Request,
    message: str = "accepted",
    data: Any | None = None,
) -> JSONResponse:
    """Return 202 Accepted with task id and status location."""
    payload = success_response(
        data={
            "task_id": task_id,
            "status_url": f"/api/v1/tasks/{task_id}",
            **(data or {}),
        },
        message=message,
        request_id=getattr(request.state, "request_id", ""),
    )
    return JSONResponse(status_code=202, content=payload)
