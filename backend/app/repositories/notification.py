"""Data access for notifications (BE-01, SEC-02)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationStatus


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        owner_id: str,
        group_id: str | None,
        source: str,
        raw_text: str,
        parsed: str | None = None,
    ) -> Notification:
        notif = Notification(
            owner_id=owner_id,
            group_id=group_id,
            source=source,
            raw_text=raw_text,
            parsed=parsed,
            status=NotificationStatus.PENDING,
        )
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def get(self, notif_id: str) -> Notification | None:
        result = await self.db.execute(
            select(Notification).where(Notification.id == notif_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[Notification]:
        result = await self.db.execute(
            select(Notification).where(Notification.owner_id == user_id)
        )
        return list(result.scalars().all())

    async def update_status(
        self, notif_id: str, status: NotificationStatus
    ) -> Notification | None:
        notif = await self.get(notif_id)
        if notif is None:
            return None
        notif.status = status
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def list_for_group(self, group_id: str) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.group_id == group_id, Notification.published.is_(True))
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def set_published(self, notif_id: str, published: bool) -> Notification | None:
        notif = await self.get(notif_id)
        if notif is None:
            return None
        notif.published = published
        await self.db.commit()
        await self.db.refresh(notif)
        return notif
