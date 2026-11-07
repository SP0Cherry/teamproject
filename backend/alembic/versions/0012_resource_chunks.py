"""create resource_chunks table with vector

Revision ID: 0012_resource_chunks
Revises: 0011_group_sync
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0012_resource_chunks"
down_revision = "0011_group_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attachment_id",
            sa.String(36),
            sa.ForeignKey("attachments.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "attachment_id", "version", "chunk_index", name="uq_chunk_version"
        ),
    )
    op.create_index("ix_resource_chunks_attachment_id", "resource_chunks", ["attachment_id"])
    op.create_index("ix_resource_chunks_owner_id", "resource_chunks", ["owner_id"])
    op.create_index("ix_resource_chunks_group_id", "resource_chunks", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_resource_chunks_group_id", table_name="resource_chunks")
    op.drop_index("ix_resource_chunks_owner_id", table_name="resource_chunks")
    op.drop_index("ix_resource_chunks_attachment_id", table_name="resource_chunks")
    op.drop_table("resource_chunks")
