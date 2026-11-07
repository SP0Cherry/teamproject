"""Data access for resource chunks (DATA-02)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_chunk import ResourceChunk


class ResourceChunkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        attachment_id: str,
        version: int,
        chunk_index: int,
        content: str,
        embedding: list[float] | None,
        owner_id: str,
        group_id: str | None,
    ) -> ResourceChunk:
        chunk = ResourceChunk(
            attachment_id=attachment_id,
            version=version,
            chunk_index=chunk_index,
            content=content,
            embedding=embedding,
            owner_id=owner_id,
            group_id=group_id,
        )
        self.db.add(chunk)
        return chunk

    async def delete_old_versions(self, attachment_id: str, current_version: int) -> None:
        """Delete chunks for versions older than current."""
        await self.db.execute(
            delete(ResourceChunk).where(
                ResourceChunk.attachment_id == attachment_id,
                ResourceChunk.version < current_version,
            )
        )

    async def delete_for_attachment(self, attachment_id: str) -> None:
        await self.db.execute(
            delete(ResourceChunk).where(ResourceChunk.attachment_id == attachment_id)
        )

    async def search_similar(
        self,
        query_embedding: list[float],
        user_id: str,
        group_ids: list[str],
        limit: int = 5,
    ) -> list[ResourceChunk]:
        """Search chunks accessible to user (owner or group member).

        Uses pgvector cosine distance on PostgreSQL; falls back to unordered
        results on SQLite (test environment).
        """
        base_stmt = select(ResourceChunk).where(
            (ResourceChunk.owner_id == user_id)
            | (ResourceChunk.group_id.in_(group_ids))
        )
        # Try pgvector ordering; fall back if not supported (SQLite)
        try:
            stmt = base_stmt.order_by(
                ResourceChunk.embedding.cosine_distance(query_embedding)
            ).limit(limit)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception:
            stmt = base_stmt.limit(limit)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
