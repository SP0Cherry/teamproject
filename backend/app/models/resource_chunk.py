"""Resource chunk model for RAG indexing (DATA-02, AI-03)."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ResourceChunk(Base, TimestampMixin):
    """A chunk of an attachment's extracted text with vector embedding."""

    __tablename__ = "resource_chunks"
    __table_args__ = (
        UniqueConstraint("attachment_id", "version", "chunk_index", name="uq_chunk_version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    attachment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attachments.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    # Denormalized for permission checks
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
