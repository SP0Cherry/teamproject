"""Data access for groups and memberships (BE-01, SEC-02)."""

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group, GroupMember, GroupRole


class GroupRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, name: str, description: str | None, owner_id: str) -> Group:
        invite_token = secrets.token_urlsafe(24)
        group = Group(
            name=name, description=description, owner_id=owner_id, invite_token=invite_token
        )
        self.db.add(group)
        await self.db.flush()
        member = GroupMember(
            group_id=group.id, user_id=owner_id, role=GroupRole.OWNER
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def get(self, group_id: str) -> Group | None:
        result = await self.db.execute(select(Group).where(Group.id == group_id))
        return result.scalar_one_or_none()

    async def get_by_invite_token(self, token: str) -> Group | None:
        result = await self.db.execute(
            select(Group).where(Group.invite_token == token)
        )
        return result.scalar_one_or_none()

    async def get_membership(
        self, group_id: str, user_id: str
    ) -> GroupMember | None:
        result = await self.db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[Group]:
        result = await self.db.execute(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def list_members(self, group_id: str) -> list[GroupMember]:
        result = await self.db.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
        return list(result.scalars().all())

    async def add_member(
        self, group_id: str, user_id: str, role: GroupRole = GroupRole.MEMBER
    ) -> GroupMember:
        existing = await self.get_membership(group_id, user_id)
        if existing:
            return existing
        member = GroupMember(group_id=group_id, user_id=user_id, role=role)
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_member(self, group_id: str, user_id: str) -> bool:
        member = await self.get_membership(group_id, user_id)
        if member is None:
            return False
        await self.db.delete(member)
        await self.db.commit()
        return True

    async def regenerate_invite_token(self, group_id: str) -> str:
        group = await self.get(group_id)
        if group is None:
            raise ValueError("group not found")
        group.invite_token = secrets.token_urlsafe(24)
        await self.db.commit()
        return group.invite_token

    async def set_sync(self, group_id: str, user_id: str, enabled: bool) -> GroupMember | None:
        member = await self.get_membership(group_id, user_id)
        if member is None:
            return None
        member.sync_enabled = enabled
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def list_synced_members(self, group_id: str) -> list[GroupMember]:
        result = await self.db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.sync_enabled.is_(True)
            )
        )
        return list(result.scalars().all())
