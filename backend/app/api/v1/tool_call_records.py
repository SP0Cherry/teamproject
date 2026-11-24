"""Tool call record query endpoint (read-only, owner-isolated)."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.openapi_docs import LOGIN_REQUIRED, responses
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.tool_call_record import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ToolCallRecordService,
    serialize,
)

router = APIRouter(prefix="/tool-call-records", tags=["tool-call-records"])


@router.get(
    "",
    summary="查询我的工具调用记录",
    description=(
        f"只读、按 owner 隔离（用户 A 查不到用户 B 的记录）。page_size 上限 {MAX_PAGE_SIZE}，"
        f"超限返回 PARAM_INVALID 400。{LOGIN_REQUIRED}"
    ),
    responses=responses(400, 401),
)
async def list_records(
    request: Request,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description=f"每页条数，上限 {MAX_PAGE_SIZE}"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await ToolCallRecordService(db).list(
        current_user.id, page, page_size
    )
    return success_response(
        data={
            "items": [serialize(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request_id=getattr(request.state, "request_id", ""),
    )
