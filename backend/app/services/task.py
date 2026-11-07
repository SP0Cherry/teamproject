"""Business layer for background tasks (BE-01, BE-02, SEC-02)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.task import BackgroundTask, TaskStatus
from app.repositories.task import TaskRepository


class TaskService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = TaskRepository(db)

    async def get_task(self, task_id: str, owner_id: str) -> BackgroundTask:
        task = await self.repo.get(task_id)
        if task is None or task.owner_id != owner_id:
            # Hide existence of unauthorized resources (SEC-02, BE-04)
            raise ApiError(
                code="RESOURCE_NOT_FOUND",
                message="task not found",
            )
        return task

    async def create_task(
        self, task_type: str, owner_id: str, result: str | None = None
    ) -> BackgroundTask:
        return await self.repo.create(task_type, owner_id, result)

    async def fail_task(self, task_id: str, error: str) -> BackgroundTask | None:
        return await self.repo.update_status(
            task_id, TaskStatus.FAILED, progress=100, error=error
        )
