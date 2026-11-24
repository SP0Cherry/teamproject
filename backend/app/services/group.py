"""Group business logic (BE-01, SEC-02, SEC-03)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.group import GroupRole
from app.repositories.group import GroupRepository
from app.services.authz import AuthzService


class GroupService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = GroupRepository(db)
        self.authz = AuthzService(db)

    async def create(self, name: str, description: str | None, owner_id: str):
        return await self.repo.create(name, description, owner_id)

    async def get(self, group_id: str, user_id: str):
        await self.authz.require_group_member(group_id, user_id)
        group = await self.repo.get(group_id)
        membership = await self.repo.get_membership(group_id, user_id)
        return group, membership

    async def list_for_user(self, user_id: str):
        return await self.repo.list_for_user(user_id)

    async def join(self, group_id: str, user_id: str):
        group = await self.repo.get(group_id)
        if group is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="group not found")
        return await self.repo.add_member(group_id, user_id)

    async def join_by_token(self, invite_token: str, user_id: str):
        group = await self.repo.get_by_invite_token(invite_token)
        if group is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="invalid invite token")
        return await self.repo.add_member(group.id, user_id)

    async def leave(self, group_id: str, user_id: str):
        membership = await self.repo.get_membership(group_id, user_id)
        if membership is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not a member")
        if membership.role == GroupRole.OWNER:
            raise ApiError(
                code="BUSINESS_RULE", message="owner cannot leave; transfer ownership first"
            )
        await self.repo.remove_member(group_id, user_id)

    async def list_members(self, group_id: str, user_id: str):
        await self.authz.require_group_member(group_id, user_id)
        return await self.repo.list_members(group_id)

    async def remove_member(self, group_id: str, target_user_id: str, admin_id: str):
        await self.authz.require_group_admin(group_id, admin_id)
        if target_user_id == admin_id:
            raise ApiError(code="BUSINESS_RULE", message="cannot remove yourself")
        target = await self.repo.get_membership(group_id, target_user_id)
        if target is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="member not found")
        if target.role == GroupRole.OWNER:
            raise ApiError(code="ACCESS_DENIED", message="cannot remove owner")
        await self.repo.remove_member(group_id, target_user_id)

    async def regenerate_invite_token(self, group_id: str, user_id: str):
        await self.authz.require_group_admin(group_id, user_id)
        return await self.repo.regenerate_invite_token(group_id)

    async def set_sync(self, group_id: str, user_id: str, enabled: bool):
        membership = await self.repo.get_membership(group_id, user_id)
        if membership is None:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="not a member")
        return await self.repo.set_sync(group_id, user_id, enabled)
