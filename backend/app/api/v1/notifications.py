"""Notification endpoints: source ingestion and user access (SEC-13, AI-02)."""

import json

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.core.source_auth import verify_source
from app.db.session import get_db
from app.models.user import User
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


class IngestRequest(BaseModel):
    text: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    group_id: str | None = None


class GroupPublishRequest(BaseModel):
    text: str = Field(min_length=1)


@router.post("/ingest")
async def ingest_notification(
    body: IngestRequest,
    request: Request,
    source: str = Depends(verify_source),
    db: AsyncSession = Depends(get_db),
):
    """Source-facing ingest endpoint. Authenticated by source shared secret."""
    service = NotificationService(db)
    notif, parsed = await service.ingest(
        raw_text=body.text,
        source=source,
        owner_id=body.owner_id,
        group_id=body.group_id,
    )
    return success_response(
        data={
            "id": notif.id,
            "status": notif.status.value,
            "candidates": parsed,
        },
        message="notification ingested",
        request_id=request.state.request_id,
    )


@router.get("")
async def list_notifications(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notifs = await service.repo.list_for_user(current_user.id)
    return success_response(
        data=[
            {
                "id": n.id,
                "source": n.source,
                "status": n.status.value,
                "raw_text": n.raw_text[:200],
            }
            for n in notifs
        ],
        request_id=request.state.request_id,
    )


@router.get("/{notification_id}")
async def get_notification(
    notification_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notif, parsed = await service.get(notification_id, current_user.id)
    return success_response(
        data={
            "id": notif.id,
            "source": notif.source,
            "status": notif.status.value,
            "raw_text": notif.raw_text,
            "candidates": parsed,
            "group_id": notif.group_id,
            "published": notif.published,
        },
        request_id=request.state.request_id,
    )


@router.post("/groups/{group_id}/publish")
async def publish_group_notification(
    group_id: str,
    body: GroupPublishRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notif, parsed = await service.publish_group_notification(
        group_id, body.text, current_user.id
    )
    return success_response(
        data={
            "id": notif.id,
            "status": notif.status.value,
            "candidates": parsed,
            "published": notif.published,
        },
        message="published",
        request_id=request.state.request_id,
    )


@router.get("/groups/{group_id}")
async def list_group_notifications(
    group_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notifs = await service.list_group_notifications(group_id, current_user.id)
    return success_response(
        data=[
            {
                "id": n.id,
                "source": n.source,
                "status": n.status.value,
                "raw_text": n.raw_text[:200],
                "published": n.published,
            }
            for n in notifs
        ],
        request_id=request.state.request_id,
    )


@router.post("/{notification_id}/withdraw")
async def withdraw_notification(
    notification_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    await service.withdraw(notification_id, current_user.id)
    return success_response(message="withdrawn", request_id=request.state.request_id)
