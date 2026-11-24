"""Data access for skills (BE-01, SEC-02). Owner-scoped, version increments on update."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill


class SkillRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, owner_id: str, name: str, capability, tool_refs: str
    ) -> Skill:
        skill = Skill(
            owner_id=owner_id,
            name=name,
            capability=capability,
            tool_refs=tool_refs,
        )
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def get_owned(self, skill_id: str, owner_id: str) -> Skill | None:
        result = await self.db.execute(
            select(Skill).where(Skill.id == skill_id, Skill.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: str) -> list[Skill]:
        result = await self.db.execute(
            select(Skill)
            .where(Skill.owner_id == owner_id)
            .order_by(Skill.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_owned(
        self, skill_id: str, owner_id: str, **fields
    ) -> Skill | None:
        skill = await self.get_owned(skill_id, owner_id)
        if skill is None:
            return None
        for key, value in fields.items():
            setattr(skill, key, value)
        skill.version = (skill.version or 1) + 1
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def delete_owned(self, skill_id: str, owner_id: str) -> Skill | None:
        skill = await self.get_owned(skill_id, owner_id)
        if skill is None:
            return None
        await self.db.delete(skill)
        await self.db.commit()
        return skill
