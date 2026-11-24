"""Tool server governance: register / connect / discover / disconnect (SEC-08)."""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.response import ApiError
from app.models.tool_server import ServerStatus, ToolServer
from app.repositories.tool_server import ToolServerRepository
from app.services.mcp_discovery import McpDiscoveryError, discover_tools


def serialize(server: ToolServer) -> dict:
    """Response projection: never includes ``token_cipher`` (SEC-08)."""
    return {
        "id": server.id,
        "name": server.name,
        "base_url": server.base_url,
        "has_token": server.has_token,
        "status": server.status.value,
        "discovered_tools": (
            json.loads(server.discovered_tools) if server.discovered_tools else []
        ),
        "last_error": server.last_error,
        "created_at": server.created_at.isoformat() if server.created_at else None,
        "updated_at": server.updated_at.isoformat() if server.updated_at else None,
    }


class ToolServerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ToolServerRepository(db)

    @staticmethod
    def _require_owner(server: ToolServer | None, owner_id: str) -> ToolServer:
        if server is None or server.owner_id != owner_id:
            # Uniform 404 so existence of others' rows is not disclosed (SEC-02).
            raise ApiError(code="RESOURCE_NOT_FOUND", message="tool server not found")
        return server

    async def register(
        self,
        owner_id: str,
        name: str,
        base_url: str,
        token: str | None,
    ) -> ToolServer:
        name = (name or "").strip()
        base_url = (base_url or "").strip()
        if not name:
            raise ApiError(code="PARAM_INVALID", message="name is required")
        if not base_url:
            raise ApiError(code="PARAM_INVALID", message="base_url is required")
        token_cipher = encrypt_secret(token) if token else None
        return await self.repo.create(
            owner_id=owner_id,
            name=name,
            base_url=base_url,
            token_cipher=token_cipher,
            has_token=bool(token),
        )

    async def list(self, owner_id: str) -> list[ToolServer]:
        return await self.repo.list_for_owner(owner_id)

    async def get(self, server_id: str, owner_id: str) -> ToolServer:
        return self._require_owner(
            await self.repo.get_owned(server_id, owner_id), owner_id
        )

    async def update(
        self,
        server_id: str,
        owner_id: str,
        name: str | None = None,
        base_url: str | None = None,
        token: str | None = None,
    ) -> ToolServer:
        fields: dict = {}
        if name is not None:
            name = name.strip()
            if not name:
                raise ApiError(code="PARAM_INVALID", message="name is required")
            fields["name"] = name
        if base_url is not None:
            base_url = base_url.strip()
            if not base_url:
                raise ApiError(code="PARAM_INVALID", message="base_url is required")
            fields["base_url"] = base_url
        if token is not None:
            # Empty string clears the stored token.
            fields["token_cipher"] = encrypt_secret(token) if token else None
            fields["has_token"] = bool(token)
        if not fields:
            raise ApiError(code="PARAM_INVALID", message="nothing to update")
        server = await self.repo.update_owned(server_id, owner_id, **fields)
        return self._require_owner(server, owner_id)

    async def delete(self, server_id: str, owner_id: str) -> ToolServer:
        server = await self.repo.delete_owned(server_id, owner_id)
        return self._require_owner(server, owner_id)

    async def connect(self, server_id: str, owner_id: str) -> ToolServer:
        server = self._require_owner(
            await self.repo.get_owned(server_id, owner_id), owner_id
        )
        token = decrypt_secret(server.token_cipher) if server.token_cipher else None
        try:
            tools = await discover_tools(server.base_url, token)
        except McpDiscoveryError as exc:
            # Any failure -> error; do not replace the existing tool list.
            server.status = ServerStatus.ERROR
            server.last_error = str(exc)
            await self.db.commit()
            await self.db.refresh(server)
            return server
        # Both steps succeeded -> connected; replace the whole tool list.
        server.status = ServerStatus.CONNECTED
        server.discovered_tools = json.dumps(tools, ensure_ascii=False)
        server.last_error = None
        await self.db.commit()
        await self.db.refresh(server)
        return server

    async def disconnect(self, server_id: str, owner_id: str) -> ToolServer:
        server = self._require_owner(
            await self.repo.get_owned(server_id, owner_id), owner_id
        )
        server.status = ServerStatus.UNCONNECTED
        server.discovered_tools = None
        server.last_error = None
        await self.db.commit()
        await self.db.refresh(server)
        return server
