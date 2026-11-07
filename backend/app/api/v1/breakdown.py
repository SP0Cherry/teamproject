"""Task breakdown endpoints (AI-06: manual confirmation required)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.breakdown import BreakdownService

router = APIRouter(prefix="/todos", tags=["breakdown"])


class ConfirmSubtasksRequest(BaseModel):
    subtasks: list[dict]


@router.get("/{todo_id}/breakdown")
async def suggest_breakdown(
    todo_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BreakdownService(db)
    subtasks = await service.suggest(todo_id, current_user.id)
    return success_response(
        data={"subtasks": subtasks}, request_id=request.state.request_id
    )


@router.post("/{todo_id}/breakdown/confirm")
async def confirm_breakdown(
    todo_id: str,
    body: ConfirmSubtasksRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = BreakdownService(db)
    created = await service.confirm_subtasks(todo_id, current_user.id, body.subtasks)
    return success_response(
        data={"created": created},
        message="subtasks created",
        request_id=request.state.request_id,
    )
