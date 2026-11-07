"""Data access for attachments (BE-01, SEC-02)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment, AttachmentStatus


class AttachmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        owner_id: str,
        group_id: str | None,
        filename: str,
        mime_type: str,
        file_size: int,
        storage_path: str,
        task_id: str | None = None,
    ) -> Attachment:
        att = Attachment(
            owner_id=owner_id,
            group_id=group_id,
            filename=filename,
            title=filename,
            mime_type=mime_type,
            file_size=file_size,
            storage_path=storage_path,
            status=AttachmentStatus.PENDING,
            task_id=task_id,
            version=1,
        )
        self.db.add(att)
        await self.db.commit()
        await self.db.refresh(att)
        return att

    async def get(self, att_id: str) -> Attachment | None:
        result = await self.db.execute(
            select(Attachment).where(Attachment.id == att_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[Attachment]:
        result = await self.db.execute(
            select(Attachment)
            .where(Attachment.owner_id == user_id, Attachment.parent_id.is_(None))
            .order_by(Attachment.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_group(self, group_id: str) -> list[Attachment]:
        result = await self.db.execute(
            select(Attachment)
            .where(Attachment.group_id == group_id, Attachment.parent_id.is_(None))
            .order_by(Attachment.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_versions(self, parent_id: str) -> list[Attachment]:
        result = await self.db.execute(
            select(Attachment)
            .where(Attachment.parent_id == parent_id)
            .order_by(Attachment.version)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        att_id: str,
        status: AttachmentStatus,
        extracted_text: str | None = None,
        error: str | None = None,
    ) -> Attachment | None:
        att = await self.get(att_id)
        if att is None:
            return None
        att.status = status
        if extracted_text is not None:
            att.extracted_text = extracted_text
        if error is not None:
            att.error = error
        await self.db.commit()
        await self.db.refresh(att)
        return att

    async def create_version(
        self,
        parent: Attachment,
        title: str,
        extracted_text: str | None,
    ) -> Attachment:
        """Create a new version derived from parent."""
        new_version = Attachment(
            owner_id=parent.owner_id,
            group_id=parent.group_id,
            filename=parent.filename,
            title=title,
            mime_type=parent.mime_type,
            file_size=parent.file_size,
            storage_path=parent.storage_path,
            status=parent.status,
            extracted_text=extracted_text,
            version=parent.version + 1,
            parent_id=parent.id,
        )
        self.db.add(new_version)
        await self.db.commit()
        await self.db.refresh(new_version)
        return new_version

    async def delete(self, att_id: str) -> bool:
        att = await self.get(att_id)
        if att is None:
            return False
        await self.db.delete(att)
        await self.db.commit()
        return True
