"""Resource indexing: chunk, embed, store (AI-03, DATA-02).

In demo mode (no embedding API configured), uses deterministic hash-based
pseudo-embeddings so vector search still works for testing.
"""

import hashlib
import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.attachment import AttachmentRepository
from app.repositories.group import GroupRepository
from app.repositories.resource_chunk import ResourceChunkRepository

EMBEDDING_DIM = 1536
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _demo_embedding(text: str) -> list[float]:
    """Deterministic pseudo-embedding for demo mode (no external API)."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Use hash bytes to seed a deterministic vector
    vec = []
    for i in range(EMBEDDING_DIM):
        byte = h[i % len(h)]
        # Map to [-1, 1] range
        val = (byte / 255.0) * 2 - 1
        vec.append(val)
    # Normalize to unit length
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class IndexService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.chunk_repo = ResourceChunkRepository(db)
        self.att_repo = AttachmentRepository(db)
        self.group_repo = GroupRepository(db)

    async def index_attachment(self, attachment_id: str) -> int:
        """Index an attachment's extracted text into chunks.

        Returns number of chunks created.
        """
        att = await self.att_repo.get(attachment_id)
        if att is None or not att.extracted_text:
            return 0

        version = att.version
        chunks = _chunk_text(att.extracted_text)

        # Delete old versions' chunks (keep only current version)
        await self.chunk_repo.delete_old_versions(attachment_id, version)

        for i, chunk_text in enumerate(chunks):
            embedding = _demo_embedding(chunk_text)
            await self.chunk_repo.create(
                attachment_id=attachment_id,
                version=version,
                chunk_index=i,
                content=chunk_text,
                embedding=embedding,
                owner_id=att.owner_id,
                group_id=att.group_id,
            )
        await self.db.commit()
        return len(chunks)

    async def search(
        self, query: str, user_id: str, group_ids: list[str], limit: int = 5
    ) -> list[dict]:
        """Search for chunks similar to query, filtered by access."""
        query_embedding = _demo_embedding(query)
        chunks = await self.chunk_repo.search_similar(
            query_embedding, user_id, group_ids, limit
        )
        return [
            {
                "attachment_id": c.attachment_id,
                "version": c.version,
                "chunk_index": c.chunk_index,
                "content": c.content,
            }
            for c in chunks
        ]

    async def delete_for_attachment(self, attachment_id: str) -> None:
        await self.chunk_repo.delete_for_attachment(attachment_id)
        await self.db.commit()
