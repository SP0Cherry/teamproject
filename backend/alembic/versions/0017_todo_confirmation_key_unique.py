"""make todos.confirmation_key unique (concurrency-safe idempotency)

Revision ID: 0017_todo_confirmation_key_unique
Revises: 0016_mcp_tool_platform
Create Date: 2026-12-02
"""
from alembic import op

revision = "0017_todo_confirmation_key_unique"
down_revision = "0016_mcp_tool_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Replace the non-unique index with a unique index. The column is nullable and a
    # unique index on a nullable column allows multiple NULLs, so todos not created
    # from a confirmation are unaffected. Items in one confirmation batch use distinct
    # per-item keys (notif:...:item:{index}), so only replayed/duplicate items collide.
    op.drop_index("ix_todos_confirmation_key", table_name="todos")
    op.create_index(
        "uq_todos_confirmation_key", "todos", ["confirmation_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_todos_confirmation_key", table_name="todos")
    op.create_index("ix_todos_confirmation_key", "todos", ["confirmation_key"])
