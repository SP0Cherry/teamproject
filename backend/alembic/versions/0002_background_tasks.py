"""create background_tasks table

Revision ID: 0002_background_tasks
Revises: 0001_pgvector
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_background_tasks"
down_revision = "0001_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "succeeded", "failed", name="task_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
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
    op.create_index("ix_background_tasks_task_type", "background_tasks", ["task_type"])
    op.create_index("ix_background_tasks_status", "background_tasks", ["status"])
    op.create_index("ix_background_tasks_owner_id", "background_tasks", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_background_tasks_owner_id", table_name="background_tasks")
    op.drop_index("ix_background_tasks_status", table_name="background_tasks")
    op.drop_index("ix_background_tasks_task_type", table_name="background_tasks")
    op.drop_table("background_tasks")
    op.execute("DROP TYPE IF EXISTS task_status;")
