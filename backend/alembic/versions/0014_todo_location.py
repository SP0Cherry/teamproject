"""add location to todos

Revision ID: 0014_todo_location
Revises: 0013_reminders
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_todo_location"
down_revision = "0013_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("todos", sa.Column("location", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("todos", "location")
