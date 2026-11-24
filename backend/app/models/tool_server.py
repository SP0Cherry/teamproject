import enum
import uuid

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ServerStatus(str, enum.Enum):
    UNCONNECTED = "unconnected"
    CONNECTED = "connected"
    ERROR = "error"


class ToolServer(Base, TimestampMixin):
    """用户登记的外部工具服务器（MCP over HTTP）。令牌对称加密存储。"""

    __tablename__ = "tool_servers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    token_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_token: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ServerStatus] = mapped_column(
        Enum(
            ServerStatus,
            name="_tool_servers_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ServerStatus.UNCONNECTED,
        index=True,
    )
    discovered_tools: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
