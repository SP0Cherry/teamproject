"""add sync_enabled to group_members

Revision ID: 0011_group_sync
Revises: 0010_notification_published
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_group_sync"
down_revision = "0010_notification_published"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_members",
        sa.Column("sync_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("group_members", "sync_enabled")
