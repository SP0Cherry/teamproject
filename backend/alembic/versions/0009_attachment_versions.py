"""add title, version, parent_id to attachments

Revision ID: 0009_attachment_versions
Revises: 0008_group_invite_token
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_attachment_versions"
down_revision = "0008_group_invite_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attachments",
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "attachments",
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.add_column(
        "attachments",
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("attachments.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attachments", "parent_id")
    op.drop_column("attachments", "version")
    op.drop_column("attachments", "title")
