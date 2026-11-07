"""Reminder service (BE-13, OPS-05)."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.reminder import ReminderStatus
from app.repositories.reminder import ReminderRepository


class ReminderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ReminderRepository(db)

    async def create(self, user_id: str, title: str, remind_at: datetime, todo_id: str | None = None):
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=timezone.utc)
        return await self.repo.create(user_id, title, remind_at, todo_id)

    async def list_pending(self, user_id: str):
        return await self.repo.list_pending(user_id)

    async def dismiss(self, reminder_id: str, user_id: str):
        reminder = await self.repo.get(reminder_id)
        if reminder is None or reminder.user_id != user_id:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        return await self.repo.set_status(reminder_id, ReminderStatus.DISMISSED)

    async def process_due(self):
        """Mark all due reminders as sent (called by worker). Dedup by status."""
        now = datetime.now(timezone.utc)
        due = await self.repo.list_due(now)
        for r in due:
            await self.repo.set_status(r.id, ReminderStatus.SENT)
        return len(due)
