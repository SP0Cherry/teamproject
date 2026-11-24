"""Todo service (BE-01, SEC-02)."""

from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.todo import TodoStatus
from app.services.date_context import validate_candidate
from app.repositories.todo import TodoRepository


class TodoService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = TodoRepository(db)

    async def list(self, user_id: str):
        return await self.repo.list_for_user(user_id)

    async def get(self, todo_id: str, user_id: str):
        todo = await self.repo.get(todo_id)
        if todo is None or todo.owner_id != user_id:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        return todo

    async def complete(self, todo_id: str, user_id: str):
        todo = await self.get(todo_id, user_id)
        todo.status = TodoStatus.DONE
        await self.repo.db.commit()
        await self.repo.db.refresh(todo)
        return todo

    async def restore(self, todo_id: str, user_id: str):
        todo = await self.get(todo_id, user_id)
        todo.status = TodoStatus.PENDING
        await self.repo.db.commit()
        await self.repo.db.refresh(todo)
        return todo

    async def batch_create(self, user_id: str, candidates: List[dict]) -> List:
        """Save confirmed todo candidates (AI-06: manual confirmation required)."""
        if not candidates:
            raise ApiError(code="PARAM_INVALID", message="no candidates")

        validated = [validate_candidate(item, i + 1) for i, item in enumerate(candidates)]
        created = [await self.repo.create(owner_id=user_id, **item) for item in validated]
        await self.repo.db.commit()
        return created
