"""Q&A endpoints (AI-01, AI-05). Streams answers as SSE (Task 7)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.logging import bind_request_id, get_logger
from app.core.openapi_docs import LOGIN_REQUIRED, responses
from app.core.response import ApiError
from app.core.sse import sse_error, sse_event
from app.db.session import get_db
from app.models.user import User
from app.services.qa import QAService

router = APIRouter(tags=["qa"])
logger = get_logger("api.qa")

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="用户问题")
    group_ids: list[str] | None = Field(
        default=None, description="可选：限定可检索资料的小组 ID 列表"
    )


@router.post(
    "/qa/ask",
    summary="流式提问",
    description=(
        "返回 `text/event-stream`。事件顺序：增量 `tool` → `meta`（含本次工具及状态，"
        "未连接/越权为 rejected）→ `data`（正文）→ `done`；流中错误以 `error` 事件返回。"
        f"{LOGIN_REQUIRED}"
    ),
    responses=responses(401),
    response_class=StreamingResponse,
)
async def ask_question(
    body: AskRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", "")
    service = QAService(db)

    async def event_gen():
        bind_request_id(request_id)
        try:
            async for evt in service.ask_stream(
                body.question, current_user.id, body.group_ids
            ):
                yield sse_event(evt["event"], evt["data"])
        except ApiError as e:
            logger.warning("qa ask business error", code=e.code)
            yield sse_error(e.code, e.message)
        except Exception:
            logger.exception("qa ask stream failed")
            yield sse_error("INTERNAL_ERROR", "提问失败")

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
