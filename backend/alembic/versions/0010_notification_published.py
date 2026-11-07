"""add published flag to notifications

Revision ID: 0010_notification_published
Revises: 0009_attachment_versions
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_notification_published"
down_revision = "0009_attachment_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("published", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_notifications_published", "notifications", ["published"])


def downgrade() -> None:
    op.drop_index("ix_notifications_published", table_name="notifications")
    op.drop_column("notifications", "published")
