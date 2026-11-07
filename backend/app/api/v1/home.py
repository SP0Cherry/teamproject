"""Home checklist endpoint (5.4)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.home import HomeService

router = APIRouter(tags=["home"])


@router.get("/home/checklist")
async def home_checklist(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = HomeService(db)
    data = await service.checklist(current_user.id)
    return success_response(data=data, request_id=request.state.request_id)
