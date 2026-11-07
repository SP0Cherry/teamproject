"""Unified access control for personal and group resources (SEC-02, SEC-03).

All authorization decisions go through this service. Personal resources are
accessible only by their owner. Group resources are accessible only by members.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.repositories.group import GroupRepository


class AuthzService:
    def __init__(self, db: AsyncSession) -> None:
        self.group_repo = GroupRepository(db)

    async def require_personal_owner(self, owner_id: str, user_id: str) -> None:
        """Allow only the owner of a personal resource."""
        if owner_id != user_id:
            raise ApiError(code="ACCESS_DENIED", message="access denied")

    async def require_group_member(self, group_id: str, user_id: str) -> None:
        """Allow only members of the group (any role)."""
        membership = await self.group_repo.get_membership(group_id, user_id)
        if membership is None:
            raise ApiError(code="ACCESS_DENIED", message="not a group member")

    async def require_group_admin(self, group_id: str, user_id: str) -> None:
        """Allow only group owner or admin."""
        from app.models.group import GroupRole

        membership = await self.group_repo.get_membership(group_id, user_id)
        if membership is None or membership.role not in (
            GroupRole.OWNER,
            GroupRole.ADMIN,
        ):
            raise ApiError(code="ACCESS_DENIED", message="group admin required")
