"""Resolve a user's skill tool refs into runtime tool definitions (Task 6.3).

For a given owner + capability, collect ``tool@server`` refs from the user's
skills, look up each referenced server (must belong to the user and be
``connected``), and emit a minimal ``{tool_name: ToolRuntime}`` map. Refs whose
server is missing, disconnected, or no longer advertises the tool are returned
in ``unavailable`` (marked ``rejected``) so the streaming ``meta`` can surface
them — graceful degradation (no blocking) while keeping the user informed
(spec: unconnected/overreach calls must show as rejected).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret
from app.models.skill import SkillCapability
from app.models.tool_server import ServerStatus
from app.repositories.skill import SkillRepository
from app.repositories.tool_server import ToolServerRepository


@dataclass
class ToolRuntime:
    name: str
    server_name: str
    base_url: str
    token: str | None
    input_schema: dict
    description: str


def _capability_enum(capability: str) -> SkillCapability | None:
    try:
        return SkillCapability(capability)
    except ValueError:
        return None


def _unavailable(ref: str, tool_name: str, server_name: str, reason: str) -> dict:
    return {
        "tool": ref,
        "name": tool_name,
        "server": server_name,
        "status": "rejected",
        "reason": reason,
        "duration_ms": 0,
    }


async def resolve_runtime_tools(
    db: AsyncSession, owner_id: str, capability: str
) -> tuple[dict[str, ToolRuntime], list[dict]]:
    """Return ``(usable_tools, unavailable_refs)``.

    ``unavailable_refs`` entries carry ``status="rejected"`` and a ``reason``
    so callers can surface them in the stream ``meta``.
    """
    if not owner_id:
        return {}, []
    target = _capability_enum(capability)
    skill_repo = SkillRepository(db)
    server_repo = ToolServerRepository(db)

    refs: list[str] = []
    for skill in await skill_repo.list_for_owner(owner_id):
        if target is not None and skill.capability != target:
            continue
        refs.extend(json.loads(skill.tool_refs) if skill.tool_refs else [])

    servers = await server_repo.list_for_owner(owner_id)
    by_name = {srv.name: srv for srv in servers}

    resolved: dict[str, ToolRuntime] = {}
    unavailable: list[dict] = []
    seen: set[str] = set()
    for ref in refs:
        if not isinstance(ref, str) or "@" not in ref:
            continue
        tool_name, server_name = ref.split("@", 1)
        if tool_name in seen:
            continue  # first occurrence wins
        seen.add(tool_name)
        srv = by_name.get(server_name)
        if srv is None:
            unavailable.append(_unavailable(ref, tool_name, server_name, "server not found"))
            continue
        if srv.status != ServerStatus.CONNECTED:
            unavailable.append(
                _unavailable(ref, tool_name, server_name, "server not connected")
            )
            continue
        tools = json.loads(srv.discovered_tools) if srv.discovered_tools else []
        match = next(
            (t for t in tools if isinstance(t, dict) and t.get("name") == tool_name),
            None,
        )
        if match is None:
            unavailable.append(
                _unavailable(ref, tool_name, server_name, "tool not advertised by server")
            )
            continue
        token = decrypt_secret(srv.token_cipher) if srv.token_cipher else None
        resolved[tool_name] = ToolRuntime(
            name=tool_name,
            server_name=server_name,
            base_url=srv.base_url,
            token=token,
            input_schema=match.get("inputSchema") or {},
            description=match.get("description") or "",
        )
    return resolved, unavailable
