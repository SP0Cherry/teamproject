"""add invite_token to groups

Revision ID: 0008_group_invite_token
Revises: 0007_todos
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_group_invite_token"
down_revision = "0007_todos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "groups",
        sa.Column("invite_token", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_groups_invite_token", "groups", ["invite_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_groups_invite_token", table_name="groups")
    op.drop_column("groups", "invite_token")
