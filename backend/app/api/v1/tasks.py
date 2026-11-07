"""Background task status endpoint (BE-02, BE-03, SEC-02)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.task import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = TaskService(db)
    task = await service.get_task(task_id, current_user.id)
    return success_response(
        data={
            "id": task.id,
            "task_type": task.task_type,
            "status": task.status.value,
            "progress": task.progress,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        },
        request_id=request.state.request_id,
    )
