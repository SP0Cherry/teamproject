"""create reminders table

Revision ID: 0013_reminders
Revises: 0012_resource_chunks
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_reminders"
down_revision = "0012_resource_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column(
            "todo_id", sa.String(36), sa.ForeignKey("todos.id"), nullable=True
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "dismissed", name="reminder_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("message", sa.Text, nullable=True),
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
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_status", "reminders", ["status"])
    op.create_index("ix_reminders_remind_at", "reminders", ["remind_at"])


def downgrade() -> None:
    op.drop_index("ix_reminders_remind_at", table_name="reminders")
    op.drop_index("ix_reminders_status", table_name="reminders")
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    op.drop_table("reminders")
    op.execute("DROP TYPE IF EXISTS reminder_status;")
