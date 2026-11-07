"""create todos table

Revision ID: 0007_todos
Revises: 0006_notifications
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_todos"
down_revision = "0006_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "todos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "done", name="todo_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "source_notification_id",
            sa.String(36),
            sa.ForeignKey("notifications.id"),
            nullable=True,
        ),
        sa.Column("confirmation_key", sa.String(64), nullable=True),
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
    op.create_index("ix_todos_owner_id", "todos", ["owner_id"])
    op.create_index("ix_todos_group_id", "todos", ["group_id"])
    op.create_index("ix_todos_status", "todos", ["status"])
    op.create_index("ix_todos_due_at", "todos", ["due_at"])
    op.create_index("ix_todos_confirmation_key", "todos", ["confirmation_key"])


def downgrade() -> None:
    op.drop_index("ix_todos_confirmation_key", table_name="todos")
    op.drop_index("ix_todos_due_at", table_name="todos")
    op.drop_index("ix_todos_status", table_name="todos")
    op.drop_index("ix_todos_group_id", table_name="todos")
    op.drop_index("ix_todos_owner_id", table_name="todos")
    op.drop_table("todos")
    op.execute("DROP TYPE IF EXISTS todo_status;")
