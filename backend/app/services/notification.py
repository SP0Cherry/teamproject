"""Notification ingestion and parsing (SEC-13, AI-02, AI-06)."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.repositories.group import GroupRepository
from app.repositories.notification import NotificationRepository
from app.services.notification_parser import extract_notification


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = NotificationRepository(db)
        self.group_repo = GroupRepository(db)

    async def ingest(
        self,
        raw_text: str,
        source: str,
        owner_id: str,
        group_id: str | None = None,
    ):
        if not raw_text or not raw_text.strip():
            raise ApiError(code="PARAM_INVALID", message="empty notification text")

        # Extract structured candidates
        parsed = await extract_notification(raw_text)
        parsed_json = json.dumps(parsed, ensure_ascii=False)

        notif = await self.repo.create(
            owner_id=owner_id,
            group_id=group_id,
            source=source,
            raw_text=raw_text,
            parsed=parsed_json,
        )
        return notif, parsed

    async def get(self, notif_id: str, user_id: str):
        notif = await self.repo.get(notif_id)
        if notif is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        # Owner can always access
        if notif.owner_id == user_id:
            parsed = json.loads(notif.parsed) if notif.parsed else None
            return notif, parsed
        # Group members can access published group notifications
        if notif.group_id and notif.published:
            membership = await self.group_repo.get_membership(notif.group_id, user_id)
            if membership:
                parsed = json.loads(notif.parsed) if notif.parsed else None
                return notif, parsed
        raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")

    async def publish_group_notification(
        self, group_id: str, raw_text: str, publisher_id: str
    ):
        """Admin publishes a group notification; synced members get a personal copy."""
        membership = await self.group_repo.get_membership(group_id, publisher_id)
        if membership is None or membership.role.value not in ("owner", "admin"):
            raise ApiError(code="ACCESS_DENIED", message="only admins can publish")

        parsed = await extract_notification(raw_text)
        parsed_json = json.dumps(parsed, ensure_ascii=False)
        notif = await self.repo.create(
            owner_id=publisher_id,
            group_id=group_id,
            source="group",
            raw_text=raw_text,
            parsed=parsed_json,
        )
        notif.published = True
        await self.db.commit()
        await self.db.refresh(notif)

        # Deliver personal copies to synced members (transactional, idempotent)
        synced = await self.group_repo.list_synced_members(group_id)
        for m in synced:
            if m.user_id == publisher_id:
                continue
            # Idempotency: skip if member already has a copy from this notification
            existing = await self.repo.list_for_user(m.user_id)
            already = any(
                n.group_id == group_id and n.source == "group-sync" and n.raw_text == raw_text
                for n in existing
            )
            if not already:
                await self.repo.create(
                    owner_id=m.user_id,
                    group_id=group_id,
                    source="group-sync",
                    raw_text=raw_text,
                    parsed=parsed_json,
                )
        return notif, parsed

    async def list_group_notifications(self, group_id: str, user_id: str):
        membership = await self.group_repo.get_membership(group_id, user_id)
        if membership is None:
            raise ApiError(code="ACCESS_DENIED", message="not a group member")
        return await self.repo.list_for_group(group_id)

    async def withdraw(self, notif_id: str, user_id: str):
        notif = await self.repo.get(notif_id)
        if notif is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        if notif.group_id:
            membership = await self.group_repo.get_membership(notif.group_id, user_id)
            if membership is None or membership.role.value not in ("owner", "admin"):
                raise ApiError(code="ACCESS_DENIED", message="only admins can withdraw")
        elif notif.owner_id != user_id:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        return await self.repo.set_published(notif_id, False)
