"""Data access for tool_servers (BE-01, SEC-02).

Every query is scoped by ``owner_id``; callers never receive rows they do not
own. Write helpers return ``None`` when the row is missing or belongs to
another user so the service layer can map it to a uniform 404.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_server import ServerStatus, ToolServer


class ToolServerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        owner_id: str,
        name: str,
        base_url: str,
        token_cipher: str | None,
        has_token: bool,
    ) -> ToolServer:
        server = ToolServer(
            owner_id=owner_id,
            name=name,
            base_url=base_url,
            token_cipher=token_cipher,
            has_token=has_token,
            status=ServerStatus.UNCONNECTED,
        )
        self.db.add(server)
        await self.db.commit()
        await self.db.refresh(server)
        return server

    async def get_owned(self, server_id: str, owner_id: str) -> ToolServer | None:
        result = await self.db.execute(
            select(ToolServer).where(
                ToolServer.id == server_id, ToolServer.owner_id == owner_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: str) -> list[ToolServer]:
        result = await self.db.execute(
            select(ToolServer)
            .where(ToolServer.owner_id == owner_id)
            .order_by(ToolServer.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_name(self, owner_id: str, name: str) -> ToolServer | None:
        result = await self.db.execute(
            select(ToolServer).where(
                ToolServer.owner_id == owner_id, ToolServer.name == name
            )
        )
        return result.scalar_one_or_none()

    async def update_owned(
        self, server_id: str, owner_id: str, **fields
    ) -> ToolServer | None:
        server = await self.get_owned(server_id, owner_id)
        if server is None:
            return None
        for key, value in fields.items():
            setattr(server, key, value)
        await self.db.commit()
        await self.db.refresh(server)
        return server

    async def delete_owned(self, server_id: str, owner_id: str) -> ToolServer | None:
        server = await self.get_owned(server_id, owner_id)
        if server is None:
            return None
        await self.db.delete(server)
        await self.db.commit()
        return server
