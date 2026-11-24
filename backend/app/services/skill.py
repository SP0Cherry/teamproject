"""Skill configuration with pre-save three-way validation (AI-09, SEC-02/11).

Before persisting ``tool_refs`` each reference ``tool@server`` is validated:
  1. format matches ``^[a-z][a-z0-9_]*@[a-z][a-z0-9-]*$``
  2. the server belongs to the current user and is ``connected``
  3. the tool name exists in that server's discovered tool list
Any failure raises ``BUSINESS_RULE`` (HTTP 422) with a readable reason.
"""

from __future__ import annotations

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.models.skill import Skill, SkillCapability
from app.models.tool_server import ServerStatus
from app.repositories.skill import SkillRepository
from app.repositories.tool_server import ToolServerRepository

_REF_RE = re.compile(r"^[a-z][a-z0-9_]*@[a-z][a-z0-9-]*$")


def serialize(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "capability": skill.capability.value,
        "tool_refs": json.loads(skill.tool_refs) if skill.tool_refs else [],
        "version": skill.version,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


class SkillService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SkillRepository(db)
        self.server_repo = ToolServerRepository(db)

    @staticmethod
    def _require_owner(skill: Skill | None, owner_id: str) -> Skill:
        if skill is None or skill.owner_id != owner_id:
            raise ApiError(code="RESOURCE_NOT_FOUND", message="skill not found")
        return skill

    async def _validate_refs(self, owner_id: str, refs) -> list[str]:
        if not isinstance(refs, list):
            raise ApiError(code="PARAM_INVALID", message="tool_refs must be a list")
        servers = await self.server_repo.list_for_owner(owner_id)
        by_name = {s.name: s for s in servers}
        for ref in refs:
            if not isinstance(ref, str) or not _REF_RE.match(ref):
                raise ApiError(
                    code="BUSINESS_RULE",
                    message=f"工具引用格式非法：{ref}（须为 tool@server）",
                )
            tool_name, server_name = ref.split("@", 1)
            server = by_name.get(server_name)
            if server is None or server.status != ServerStatus.CONNECTED:
                raise ApiError(
                    code="BUSINESS_RULE",
                    message=f"服务器 {server_name} 不存在或未连接",
                )
            tools = json.loads(server.discovered_tools) if server.discovered_tools else []
            tool_names = {t.get("name") for t in tools if isinstance(t, dict)}
            if tool_name not in tool_names:
                raise ApiError(
                    code="BUSINESS_RULE",
                    message=f"工具 {tool_name} 不在服务器 {server_name} 的发现清单中",
                )
        return refs

    @staticmethod
    def _parse_capability(capability: str) -> SkillCapability:
        try:
            return SkillCapability(capability)
        except ValueError:
            raise ApiError(
                code="PARAM_INVALID",
                message="capability must be qa or notification_extraction",
            ) from None

    async def create(
        self, owner_id: str, name: str, capability: str, tool_refs: list[str] | None
    ) -> Skill:
        name = (name or "").strip()
        if not name:
            raise ApiError(code="PARAM_INVALID", message="name is required")
        cap = self._parse_capability(capability)
        await self._validate_refs(owner_id, tool_refs or [])
        return await self.repo.create(
            owner_id=owner_id,
            name=name,
            capability=cap,
            tool_refs=json.dumps(tool_refs or [], ensure_ascii=False),
        )

    async def list(self, owner_id: str) -> list[Skill]:
        return await self.repo.list_for_owner(owner_id)

    async def get(self, skill_id: str, owner_id: str) -> Skill:
        return self._require_owner(
            await self.repo.get_owned(skill_id, owner_id), owner_id
        )

    async def update(
        self,
        skill_id: str,
        owner_id: str,
        name: str | None = None,
        capability: str | None = None,
        tool_refs: list[str] | None = None,
    ) -> Skill:
        fields: dict = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ApiError(code="PARAM_INVALID", message="name is required")
            fields["name"] = name
        if capability is not None:
            fields["capability"] = self._parse_capability(capability)
        if tool_refs is not None:
            await self._validate_refs(owner_id, tool_refs)
            fields["tool_refs"] = json.dumps(tool_refs, ensure_ascii=False)
        if not fields:
            raise ApiError(code="PARAM_INVALID", message="nothing to update")
        skill = await self.repo.update_owned(skill_id, owner_id, **fields)
        return self._require_owner(skill, owner_id)

    async def delete(self, skill_id: str, owner_id: str) -> Skill:
        return self._require_owner(
            await self.repo.delete_owned(skill_id, owner_id), owner_id
        )
