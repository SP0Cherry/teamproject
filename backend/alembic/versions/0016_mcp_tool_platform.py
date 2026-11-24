"""create tool_servers / skills / tool_call_records tables

Revision ID: 0016_mcp_tool_platform
Revises: 0015_todo_time_precision
Create Date: 2026-12-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_mcp_tool_platform"
down_revision = "0015_todo_time_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_servers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("token_cipher", sa.Text, nullable=True),
        sa.Column("has_token", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "status",
            sa.Enum("unconnected", "connected", "error", name="_tool_servers_status"),
            nullable=False,
            server_default="unconnected",
        ),
        sa.Column("discovered_tools", sa.Text, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
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
    op.create_index("ix_tool_servers_owner_id", "tool_servers", ["owner_id"])
    op.create_index("ix_tool_servers_status", "tool_servers", ["status"])

    op.create_table(
        "skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "capability",
            sa.Enum("qa", "notification_extraction", name="_skills_capability"),
            nullable=False,
        ),
        sa.Column("tool_refs", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
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
    op.create_index("ix_skills_owner_id", "skills", ["owner_id"])
    op.create_index("ix_skills_capability", "skills", ["capability"])

    op.create_table(
        "tool_call_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("server_name", sa.String(128), nullable=True),
        sa.Column("server_id", sa.String(36), nullable=True),
        sa.Column(
            "result",
            sa.Enum("success", "rejected", "error", name="_tool_call_records_result"),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.String(64), nullable=True),
        sa.Column("round_index", sa.Integer, nullable=True),
        sa.Column("triggered_by", sa.String(36), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
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
    op.create_index("ix_tool_call_records_owner_id", "tool_call_records", ["owner_id"])
    op.create_index("ix_tool_call_records_result", "tool_call_records", ["result"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_records_result", table_name="tool_call_records")
    op.drop_index("ix_tool_call_records_owner_id", table_name="tool_call_records")
    op.drop_table("tool_call_records")
    op.execute("DROP TYPE IF EXISTS _tool_call_records_result;")

    op.drop_index("ix_skills_capability", table_name="skills")
    op.drop_index("ix_skills_owner_id", table_name="skills")
    op.drop_table("skills")
    op.execute("DROP TYPE IF EXISTS _skills_capability;")

    op.drop_index("ix_tool_servers_status", table_name="tool_servers")
    op.drop_index("ix_tool_servers_owner_id", table_name="tool_servers")
    op.drop_table("tool_servers")
    op.execute("DROP TYPE IF EXISTS _tool_servers_status;")
