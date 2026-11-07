"""Data access layer for background tasks (BE-01, BE-06)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import BackgroundTask, TaskStatus


class TaskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, task_id: str) -> BackgroundTask | None:
        result = await self.db.execute(
            select(BackgroundTask).where(BackgroundTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, task_type: str, owner_id: str, result: str | None = None
    ) -> BackgroundTask:
        task = BackgroundTask(
            task_type=task_type,
            owner_id=owner_id,
            status=TaskStatus.PENDING,
            result=result,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int | None = None,
        error: str | None = None,
        result: str | None = None,
    ) -> BackgroundTask | None:
        task = await self.get(task_id)
        if task is None:
            return None
        task.status = status
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error = error
        if result is not None:
            task.result = result
        task.attempts += 1
        await self.db.commit()
        await self.db.refresh(task)
        return task
