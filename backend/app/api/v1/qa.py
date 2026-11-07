"""Q&A endpoints (AI-01, AI-05)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.qa import QAService

router = APIRouter(tags=["qa"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    group_ids: list[str] | None = None


@router.post("/qa/ask")
async def ask_question(
    body: AskRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = QAService(db)
    result = await service.ask(
        body.question, current_user.id, body.group_ids
    )
    return success_response(data=result, request_id=request.state.request_id)
