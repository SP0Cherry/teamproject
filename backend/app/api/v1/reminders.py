"""Reminder endpoints (5.3)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.reminder import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


class CreateReminderRequest(BaseModel):
    title: str = Field(min_length=1)
    remind_at: str
    todo_id: str | None = None


@router.post("")
async def create_reminder(
    body: CreateReminderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReminderService(db)
    remind_at = datetime.fromisoformat(body.remind_at)
    r = await service.create(current_user.id, body.title, remind_at, body.todo_id)
    return success_response(
        data={"id": r.id, "title": r.title, "remind_at": r.remind_at.isoformat()},
        message="reminder created",
        request_id=request.state.request_id,
    )


@router.get("")
async def list_reminders(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReminderService(db)
    reminders = await service.list_pending(current_user.id)
    return success_response(
        data=[
            {
                "id": r.id,
                "title": r.title,
                "remind_at": r.remind_at.isoformat(),
                "status": r.status.value,
            }
            for r in reminders
        ],
        request_id=request.state.request_id,
    )


@router.post("/{reminder_id}/dismiss")
async def dismiss_reminder(
    reminder_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReminderService(db)
    await service.dismiss(reminder_id, current_user.id)
    return success_response(message="dismissed", request_id=request.state.request_id)
