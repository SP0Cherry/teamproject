"""create attachments table

Revision ID: 0005_attachments
Revises: 0004_groups
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_attachments"
down_revision = "0004_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "succeeded", "failed", name="attachment_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("error", sa.String(512), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=True),
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
    )
    op.create_index("ix_attachments_owner_id", "attachments", ["owner_id"])
    op.create_index("ix_attachments_group_id", "attachments", ["group_id"])
    op.create_index("ix_attachments_status", "attachments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_attachments_status", table_name="attachments")
    op.drop_index("ix_attachments_group_id", table_name="attachments")
    op.drop_index("ix_attachments_owner_id", table_name="attachments")
    op.drop_table("attachments")
    op.execute("DROP TYPE IF EXISTS attachment_status;")
