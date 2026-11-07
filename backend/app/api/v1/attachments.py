"""Attachment upload and status endpoints (SEC-08, BE-13)."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_response import accepted_response
from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.attachment import AttachmentService

router = APIRouter(prefix="/attachments", tags=["attachments"])


class EditAttachmentRequest(BaseModel):
    title: str | None = None
    extracted_text: str | None = None


@router.post("")
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    group_id: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AttachmentService(db)
    att, task = await service.upload(file, current_user.id, group_id=group_id)
    return accepted_response(
        task_id=task.id,
        request=request,
        message="upload accepted, processing",
        data={
            "attachment_id": att.id,
            "filename": att.filename,
            "size": att.file_size,
            "group_id": att.group_id,
        },
    )


@router.get("")
async def list_attachments(
    request: Request,
    group_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AttachmentService(db)
    atts = await service.list(current_user.id, group_id=group_id)
    return success_response(
        data=[
            {
                "id": a.id,
                "filename": a.filename,
                "title": a.title,
                "mime_type": a.mime_type,
                "file_size": a.file_size,
                "status": a.status.value,
                "group_id": a.group_id,
                "version": a.version,
            }
            for a in atts
        ],
        request_id=request.state.request_id,
    )


@router.get("/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AttachmentService(db)
    att = await service.get(attachment_id, current_user.id)
    return success_response(
        data={
            "id": att.id,
            "filename": att.filename,
            "title": att.title,
            "mime_type": att.mime_type,
            "file_size": att.file_size,
            "status": att.status.value,
            "extracted_text": att.extracted_text,
            "error": att.error,
            "task_id": att.task_id,
            "group_id": att.group_id,
            "version": att.version,
        },
        request_id=request.state.request_id,
    )


@router.put("/{attachment_id}")
async def edit_attachment(
    attachment_id: str,
    body: EditAttachmentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AttachmentService(db)
    att = await service.edit(
        attachment_id, current_user.id, body.title, body.extracted_text
    )
    return success_response(
        data={"id": att.id, "title": att.title, "version": att.version},
        message="updated",
        request_id=request.state.request_id,
    )


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AttachmentService(db)
    await service.delete(attachment_id, current_user.id)
    return success_response(message="deleted", request_id=request.state.request_id)


@router.post("/{attachment_id}/index")
async def index_attachment(
    attachment_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Index attachment's extracted text into vector chunks for RAG."""
    from app.services.indexer import IndexService
    from app.services.attachment import AttachmentService

    att_service = AttachmentService(db)
    att = await att_service.get(attachment_id, current_user.id)
    idx = IndexService(db)
    count = await idx.index_attachment(att.id)
    return success_response(
        data={"chunks_indexed": count},
        message="indexed",
        request_id=request.state.request_id,
    )
