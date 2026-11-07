"""Notification confirmation: convert candidates to todos atomically (BE-14, AI-06).

The confirmation is idempotent: retrying or concurrent confirmation with the same
notification produces only one batch of todos, identified by a confirmation_key.
"""

import hashlib
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.notification import NotificationStatus
from app.models.todo import TodoStatus
from app.repositories.group import GroupRepository
from app.repositories.notification import NotificationRepository
from app.repositories.todo import TodoRepository


class ConfirmationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.notif_repo = NotificationRepository(db)
        self.todo_repo = TodoRepository(db)
        self.group_repo = GroupRepository(db)

    async def confirm(
        self,
        notification_id: str,
        user_id: str,
        candidates: list[dict],
    ) -> list:
        """Confirm notification candidates and create todos in one transaction.

        Idempotent: if already confirmed, returns existing todos.
        """
        notif = await self.notif_repo.get(notification_id)
        if notif is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        # Owner or group member (for published group notifications) can confirm
        if notif.owner_id != user_id:
            if notif.group_id and notif.published:
                membership = await self.group_repo.get_membership(notif.group_id, user_id)
                if membership is None:
                    raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
            else:
                raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")

        # Idempotency key: per-user for group notifications (each member confirms independently)
        confirmation_key = f"notif:{notification_id}:user:{user_id}"

        # If already confirmed, return existing todos (idempotency)
        existing = await self.todo_repo.list_by_confirmation_key(confirmation_key)
        if existing:
            return [
                {"id": t.id, "title": t.title, "status": t.status.value}
                for t in existing
            ]

        # Validate candidates
        if not candidates:
            raise ApiError(code="PARAM_INVALID", message="no candidates to confirm")

        created = []
        for item in candidates:
            title = item.get("title") or item.get("text")
            if not title or not str(title).strip():
                raise ApiError(
                    code="PARAM_INVALID", message="candidate missing title"
                )
            due_at = None
            deadline = item.get("deadline")
            if deadline:
                try:
                    due_at = datetime.fromisoformat(deadline)
                except (ValueError, TypeError):
                    due_at = None
            todo = await self.todo_repo.create(
                owner_id=user_id,
                title=str(title).strip(),
                description=item.get("description"),
                due_at=due_at,
                group_id=notif.group_id,
                source_notification_id=notification_id,
                confirmation_key=confirmation_key,
            )
            created.append(todo)

        # Mark notification as confirmed
        await self.notif_repo.update_status(
            notification_id, NotificationStatus.CONFIRMED
        )
        await self.db.commit()

        return [
            {"id": t.id, "title": t.title, "status": t.status.value} for t in created
        ]

    async def discard(self, notification_id: str, user_id: str) -> None:
        notif = await self.notif_repo.get(notification_id)
        if notif is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        if notif.owner_id != user_id:
            if notif.group_id:
                membership = await self.group_repo.get_membership(notif.group_id, user_id)
                if membership is None or membership.role.value not in ("owner", "admin"):
                    raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
            else:
                raise ApiError(code="RESOURCE_NOT_FOUND", message="not found")
        await self.notif_repo.update_status(notification_id, NotificationStatus.DISCARDED)
        await self.db.commit()
