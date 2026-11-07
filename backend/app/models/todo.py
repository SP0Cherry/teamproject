import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TodoStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"


class Todo(Base, TimestampMixin):
    __tablename__ = "todos"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    group_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("groups.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[TodoStatus] = mapped_column(
        Enum(TodoStatus, name="todo_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=TodoStatus.PENDING, index=True
    )
    source_notification_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("notifications.id"), nullable=True
    )
    # Idempotency key: confirmation batch id from a notification
    confirmation_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
