"""Attachment upload service with quota validation and extraction (SEC-02, BE-13)."""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.response import ApiError
from app.models.attachment import AttachmentStatus
from app.repositories.attachment import AttachmentRepository
from app.repositories.group import GroupRepository
from app.services.extractor import ALLOWED_MIME_TYPES
from app.services.task import TaskService


class AttachmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AttachmentRepository(db)
        self.group_repo = GroupRepository(db)
        self.task_service = TaskService(db)

    async def upload(
        self,
        file: UploadFile,
        owner_id: str,
        group_id: str | None = None,
    ):
        # Validate scope: if group_id, user must be a member
        if group_id:
            membership = await self.group_repo.get_membership(group_id, owner_id)
            if membership is None:
                raise ApiError(code="ACCESS_DENIED", message="not a group member")

        # Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise ApiError(
                code="PARAM_INVALID",
                message=f"unsupported file type: {file.content_type}",
            )

        # Validate file size (SEC-08: quota)
        max_bytes = settings.max_upload_mb * 1024 * 1024
        content = await file.read()
        if len(content) == 0:
            raise ApiError(code="PARAM_INVALID", message="empty file")
        if len(content) > max_bytes:
            raise ApiError(
                code="PARAM_INVALID",
                message=f"file exceeds {settings.max_upload_mb}MB limit",
            )

        # Save to private storage (SEC-08: not web-accessible)
        ext = ALLOWED_MIME_TYPES[file.content_type]
        stored_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = Path(settings.upload_dir) / stored_name
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(content)

        # Create background task for extraction
        task = await self.task_service.create_task(
            task_type="extract", owner_id=owner_id
        )

        att = await self.repo.create(
            owner_id=owner_id,
            group_id=group_id,
            filename=file.filename or stored_name,
            mime_type=file.content_type,
            file_size=len(content),
            storage_path=str(storage_path),
            task_id=task.id,
        )
        return att, task

    async def get(self, att_id: str, user_id: str):
        att = await self.repo.get(att_id)
        if att is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        # Authorization: owner or group member
        if att.owner_id == user_id:
            return att
        if att.group_id:
            membership = await self.group_repo.get_membership(att.group_id, user_id)
            if membership:
                return att
        # Return 404 to avoid leaking resource existence (SEC-02)
        raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")

    async def list(self, user_id: str, group_id: str | None = None):
        if group_id:
            membership = await self.group_repo.get_membership(group_id, user_id)
            if membership is None:
                raise ApiError(code="ACCESS_DENIED", message="not a group member")
            return await self.repo.list_for_group(group_id)
        return await self.repo.list_for_user(user_id)

    async def edit(
        self, att_id: str, user_id: str, title: str | None, extracted_text: str | None
    ):
        att = await self.get(att_id, user_id)
        # Only owner or group admin can edit
        if att.owner_id != user_id:
            if att.group_id:
                membership = await self.group_repo.get_membership(att.group_id, user_id)
                if not membership or membership.role.value not in ("owner", "admin"):
                    raise ApiError(code="ACCESS_DENIED", message="cannot edit")
            else:
                raise ApiError(code="ACCESS_DENIED", message="cannot edit")
        new_title = title if title is not None else att.title
        new_text = extracted_text if extracted_text is not None else att.extracted_text
        # Create new version (BE-14: immutable original, versioning)
        return await self.repo.create_version(att, new_title, new_text)

    async def delete(self, att_id: str, user_id: str):
        att = await self.get(att_id, user_id)
        if att.owner_id != user_id:
            if att.group_id:
                membership = await self.group_repo.get_membership(att.group_id, user_id)
                if not membership or membership.role.value not in ("owner", "admin"):
                    raise ApiError(code="ACCESS_DENIED", message="cannot delete")
            else:
                raise ApiError(code="ACCESS_DENIED", message="cannot delete")
        # Clean up vector chunks (DATA-02: cross-store deletion)
        from app.services.indexer import IndexService
        await IndexService(self.db).delete_for_attachment(att_id)
        # Delete file from storage
        try:
            path = Path(settings.upload_dir) / att.storage_path
            if path.exists():
                path.unlink()
        except Exception:
            pass  # Best-effort cleanup
        await self.repo.delete(att_id)

    async def process_extraction(self, att_id: str, ocr_fn=None) -> None:
        """Run text extraction and update attachment status (called by worker)."""
        from app.services.extractor import extract_text

        att = await self.repo.get(att_id)
        if att is None:
            return
        await self.repo.update_status(att_id, AttachmentStatus.PROCESSING)
        text, err = extract_text(att.storage_path, att.mime_type, ocr_fn)
        if err:
            await self.repo.update_status(att_id, AttachmentStatus.FAILED, error=err)
        else:
            await self.repo.update_status(
                att_id, AttachmentStatus.SUCCEEDED, extracted_text=text
            )
