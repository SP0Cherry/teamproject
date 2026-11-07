"""Home page checklist service (5.4)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.todo import TodoRepository


class HomeService:
    def __init__(self, db: AsyncSession) -> None:
        self.todo_repo = TodoRepository(db)

    async def checklist(self, user_id: str) -> dict:
        todos = await self.todo_repo.list_for_user(user_id)
        now = datetime.now(timezone.utc)
        today_end = now.replace(hour=23, minute=59, second=59)
        seven_days = now + timedelta(days=7)

        overdue = []
        today = []
        upcoming = []

        for t in todos:
            if t.status.value == "done":
                continue
            due = t.due_at
            if due is None:
                upcoming.append(t)
                continue
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < now:
                overdue.append(t)
            elif due <= today_end:
                today.append(t)
            elif due <= seven_days:
                upcoming.append(t)
            else:
                upcoming.append(t)

        return {
            "overdue": [self._serialize(t) for t in overdue],
            "today": [self._serialize(t) for t in today],
            "upcoming": [self._serialize(t) for t in upcoming],
            "updated_at": now.isoformat(),
        }

    @staticmethod
    def _serialize(t) -> dict:
        return {
            "id": t.id,
            "title": t.title,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "status": t.status.value,
        }
