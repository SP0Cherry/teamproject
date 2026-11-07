"""Data access for reminders."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder, ReminderStatus


class ReminderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, user_id: str, title: str, remind_at: datetime, todo_id: str | None = None
    ) -> Reminder:
        r = Reminder(
            user_id=user_id,
            title=title,
            remind_at=remind_at,
            todo_id=todo_id,
            status=ReminderStatus.PENDING,
        )
        self.db.add(r)
        await self.db.commit()
        await self.db.refresh(r)
        return r

    async def get(self, reminder_id: str) -> Reminder | None:
        result = await self.db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        return result.scalar_one_or_none()

    async def list_pending(self, user_id: str) -> list[Reminder]:
        result = await self.db.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.status == ReminderStatus.PENDING)
            .order_by(Reminder.remind_at)
        )
        return list(result.scalars().all())

    async def list_due(self, now: datetime) -> list[Reminder]:
        result = await self.db.execute(
            select(Reminder).where(
                Reminder.status == ReminderStatus.PENDING,
                Reminder.remind_at <= now,
            )
        )
        return list(result.scalars().all())

    async def set_status(self, reminder_id: str, status: ReminderStatus) -> Reminder | None:
        r = await self.get(reminder_id)
        if r is None:
            return None
        r.status = status
        await self.db.commit()
        return r
