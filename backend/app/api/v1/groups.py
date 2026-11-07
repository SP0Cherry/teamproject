"""Group endpoints (SEC-02, SEC-03)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.services.group import GroupService

router = APIRouter(prefix="/groups", tags=["groups"])


class CreateGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


class JoinGroupRequest(BaseModel):
    group_id: str = Field(min_length=1)


class JoinByTokenRequest(BaseModel):
    invite_token: str = Field(min_length=1)


@router.post("")
async def create_group(
    body: CreateGroupRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    group = await service.create(body.name, body.description, current_user.id)
    return success_response(
        data={"id": group.id, "name": group.name, "invite_token": group.invite_token},
        message="group created",
        request_id=request.state.request_id,
    )


@router.get("")
async def list_groups(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    groups = await service.list_for_user(current_user.id)
    return success_response(
        data=[{"id": g.id, "name": g.name} for g in groups],
        request_id=request.state.request_id,
    )


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    group = await service.get(group_id, current_user.id)
    return success_response(
        data={
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "invite_token": group.invite_token,
        },
        request_id=request.state.request_id,
    )


@router.post("/{group_id}/join")
async def join_group(
    group_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    member = await service.join(group_id, current_user.id)
    return success_response(
        data={"group_id": member.group_id, "role": member.role.value},
        message="joined",
        request_id=request.state.request_id,
    )


@router.post("/join-by-token")
async def join_by_token(
    body: JoinByTokenRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    member = await service.join_by_token(body.invite_token, current_user.id)
    return success_response(
        data={"group_id": member.group_id, "role": member.role.value},
        message="joined",
        request_id=request.state.request_id,
    )


@router.post("/{group_id}/leave")
async def leave_group(
    group_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    await service.leave(group_id, current_user.id)
    return success_response(message="left", request_id=request.state.request_id)


@router.get("/{group_id}/members")
async def list_members(
    group_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    members = await service.list_members(group_id, current_user.id)
    return success_response(
        data=[{"user_id": m.user_id, "role": m.role.value} for m in members],
        request_id=request.state.request_id,
    )


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: str,
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    await service.remove_member(group_id, user_id, current_user.id)
    return success_response(message="removed", request_id=request.state.request_id)


@router.post("/{group_id}/regenerate-invite-token")
async def regenerate_invite_token(
    group_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    token = await service.regenerate_invite_token(group_id, current_user.id)
    return success_response(
        data={"invite_token": token}, request_id=request.state.request_id
    )


class SetSyncRequest(BaseModel):
    enabled: bool


@router.put("/{group_id}/sync")
async def set_sync(
    group_id: str,
    body: SetSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    member = await service.set_sync(group_id, current_user.id, body.enabled)
    return success_response(
        data={"sync_enabled": member.sync_enabled},
        request_id=request.state.request_id,
    )
