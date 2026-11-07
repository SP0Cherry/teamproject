"""create notifications table

Revision ID: 0006_notifications
Revises: 0005_attachments
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_notifications"
down_revision = "0005_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "discarded", name="notification_status"),
            nullable=False,
            server_default="pending",
        ),
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
    op.create_index("ix_notifications_owner_id", "notifications", ["owner_id"])
    op.create_index("ix_notifications_group_id", "notifications", ["group_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])


def downgrade() -> None:
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_group_id", table_name="notifications")
    op.drop_index("ix_notifications_owner_id", table_name="notifications")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notification_status;")
