"""Data access for todos (BE-01, SEC-02)."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.todo import Todo, TodoStatus


class TodoRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        owner_id: str,
        title: str,
        description: str | None = None,
        location: str | None = None,
        due_at: datetime | None = None,
        due_date: date | None = None,
        due_precision: str | None = None,
        due_timezone: str = "Asia/Shanghai",
        group_id: str | None = None,
        source_notification_id: str | None = None,
        confirmation_key: str | None = None,
    ) -> Todo:
        todo = Todo(
            owner_id=owner_id,
            group_id=group_id,
            title=title,
            description=description,
            location=location,
            due_at=due_at,
            due_date=due_date,
            due_precision=due_precision or ("datetime" if due_at else "date" if due_date else "unknown"),
            due_timezone=due_timezone,
            status=TodoStatus.PENDING,
            source_notification_id=source_notification_id,
            confirmation_key=confirmation_key,
        )
        self.db.add(todo)
        return todo

    async def get(self, todo_id: str) -> Todo | None:
        result = await self.db.execute(select(Todo).where(Todo.id == todo_id))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[Todo]:
        result = await self.db.execute(
            select(Todo)
            .where(Todo.owner_id == user_id)
            .order_by(Todo.due_at.is_(None), Todo.due_at, Todo.created_at)
        )
        return list(result.scalars().all())

    async def list_by_confirmation_key(self, key: str) -> list[Todo]:
        result = await self.db.execute(
            select(Todo).where(Todo.confirmation_key == key)
        )
        return list(result.scalars().all())

    async def list_by_confirmation_batch(self, batch_prefix: str) -> list[Todo]:
        """Return all todos belonging to one confirmation batch.

        Items in a batch share the prefix ``notif:{notification_id}:user:{user_id}``
        and differ by the trailing ``:item:{index}``. UUIDs contain no colons or LIKE
        wildcards, so the prefix is unambiguous.
        """
        result = await self.db.execute(
            select(Todo).where(Todo.confirmation_key.like(f"{batch_prefix}:item:%"))
        )
        return list(result.scalars().all())

    async def update_status(self, todo_id: str, status: TodoStatus) -> Todo | None:
        todo = await self.get(todo_id)
        if todo is None:
            return None
        todo.status = status
        return todo
