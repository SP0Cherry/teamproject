import enum
import uuid

from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ToolCallResult(str, enum.Enum):
    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"


class ToolCallRecord(Base, TimestampMixin):
    """工具调用记录（只增不改）。不含参数与结果正文，仅留存元数据。"""

    __tablename__ = "tool_call_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    server_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    server_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[ToolCallResult] = mapped_column(
        Enum(
            ToolCallResult,
            name="_tool_call_records_result",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    round_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(36), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
