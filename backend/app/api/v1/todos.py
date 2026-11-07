"""Confirmation and todo endpoints (BE-14, AI-06)."""

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.confirmation import ConfirmationService
from app.services.extractor import ALLOWED_MIME_TYPES, extract_text
from app.services.todo import TodoService
from app.services.todo_parser import parse_todos

router = APIRouter(tags=["todos"])


class ConfirmRequest(BaseModel):
    candidates: list[dict] = Field(min_length=1)


class LLMConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ParseTextRequest(BaseModel):
    text: str = Field(min_length=1)
    llm_config: LLMConfig | None = None


class BatchCreateRequest(BaseModel):
    todos: list[dict] = Field(min_length=1)


@router.post("/todos/parse-text")
async def parse_todos_from_text(
    body: ParseTextRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Parse arbitrary text into todo candidates (not saved, AI-06)."""
    llm_cfg = body.llm_config.model_dump() if body.llm_config else None
    result = await parse_todos(body.text, llm_config=llm_cfg)
    return success_response(
        data={"candidates": result["candidates"], "parser": result["parser"]},
        request_id=request.state.request_id,
    )


@router.post("/todos/parse-file")
async def parse_todos_from_file(
    request: Request,
    file: UploadFile = File(...),
    llm_config: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file, extract text, parse into todo candidates (not saved, AI-06)."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        from app.core.response import ApiError
        raise ApiError(code="PARAM_INVALID", message="unsupported file type")

    content = await file.read()
    ext = ALLOWED_MIME_TYPES[file.content_type]
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        text, err = extract_text(tmp_path, file.content_type)
        if err:
            from app.core.response import ApiError
            raise ApiError(code="BUSINESS_RULE", message=f"extraction failed: {err}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    llm_cfg = None
    if llm_config:
        try:
            llm_cfg = json.loads(llm_config)
        except json.JSONDecodeError:
            llm_cfg = None

    result = await parse_todos(text, llm_config=llm_cfg)
    return success_response(
        data={
            "candidates": result["candidates"],
            "parser": result["parser"],
            "extracted_text": text[:2000],
        },
        request_id=request.state.request_id,
    )


@router.post("/todos/batch-create")
async def batch_create_todos(
    body: BatchCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save confirmed todo candidates to database (AI-06: manual confirmation)."""
    service = TodoService(db)
    created = await service.batch_create(current_user.id, body.todos)
    return success_response(
        data=[
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "location": t.location,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "status": t.status.value,
            }
            for t in created
        ],
        message="created",
        request_id=request.state.request_id,
    )


@router.get("/todos")
async def list_todos(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TodoService(db)
    todos = await service.list(current_user.id)
    return success_response(
        data=[
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "location": t.location,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "status": t.status.value,
            }
            for t in todos
        ],
        request_id=request.state.request_id,
    )


@router.get("/todos/{todo_id}")
async def get_todo(
    todo_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TodoService(db)
    todo = await service.get(todo_id, current_user.id)
    return success_response(
        data={
            "id": todo.id,
            "title": todo.title,
            "description": todo.description,
            "location": todo.location,
            "due_at": todo.due_at.isoformat() if todo.due_at else None,
            "status": todo.status.value,
        },
        request_id=request.state.request_id,
    )


@router.post("/notifications/{notification_id}/confirm")
async def confirm_notification(
    notification_id: str,
    body: ConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConfirmationService(db)
    todos = await service.confirm(notification_id, current_user.id, body.candidates)
    return success_response(
        data=todos, message="confirmed", request_id=request.state.request_id
    )


@router.post("/notifications/{notification_id}/discard")
async def discard_notification(
    notification_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConfirmationService(db)
    await service.discard(notification_id, current_user.id)
    return success_response(message="discarded", request_id=request.state.request_id)


@router.post("/todos/{todo_id}/complete")
async def complete_todo(
    todo_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TodoService(db)
    todo = await service.complete(todo_id, current_user.id)
    return success_response(
        data={"id": todo.id, "status": todo.status.value},
        request_id=request.state.request_id,
    )


@router.post("/todos/{todo_id}/restore")
async def restore_todo(
    todo_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TodoService(db)
    todo = await service.restore(todo_id, current_user.id)
    return success_response(
        data={"id": todo.id, "status": todo.status.value},
        request_id=request.state.request_id,
    )
