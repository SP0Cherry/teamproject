"""Notification confirmation: convert candidates to todos atomically (BE-14, AI-06).

The confirmation is idempotent: retrying or concurrent confirmation with the same
notification produces only one batch of todos, identified by a confirmation_key.
"""

import hashlib
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.notification import NotificationStatus
from app.models.todo import TodoStatus
from app.services.date_context import validate_candidate, serialize_todo
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

        # Batch prefix shared by every item in this confirmation. Per-item keys append
        # ":item:{index}" so items in the same batch don't collide, while a replayed
        # batch reproduces identical keys and is blocked by the unique index on the
        # column (concurrency-safe idempotency).
        batch_prefix = f"notif:{notification_id}:user:{user_id}"

        # If already confirmed, return existing todos (idempotency)
        existing = await self.todo_repo.list_by_confirmation_batch(batch_prefix)
        if existing:
            return [serialize_todo(t) for t in existing]

        # Validate candidates
        if not candidates:
            raise ApiError(code="PARAM_INVALID", message="no candidates to confirm")

        validated = [validate_candidate(item, i + 1) for i, item in enumerate(candidates)]
        try:
            created = []
            for i, item in enumerate(validated):
                todo = await self.todo_repo.create(
                    owner_id=user_id,
                    group_id=notif.group_id,
                    source_notification_id=notification_id,
                    confirmation_key=f"{batch_prefix}:item:{i}",
                    **item,
                )
                created.append(todo)

            # Mark notification as confirmed
            await self.notif_repo.update_status(
                notification_id, NotificationStatus.CONFIRMED
            )
            await self.db.commit()
        except IntegrityError:
            # Lost a concurrent confirmation race: roll back our partial inserts and
            # return the batch that won the race (no duplicate data, no error to caller).
            await self.db.rollback()
            existing = await self.todo_repo.list_by_confirmation_batch(batch_prefix)
            return [serialize_todo(t) for t in existing]

        return [serialize_todo(t) for t in created]

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
