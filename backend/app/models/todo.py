import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Boolean, DateTime, Enum, ForeignKey, String, Text
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
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_precision: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    due_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai")
    __table_args__ = (CheckConstraint("(due_precision = 'datetime' AND due_at IS NOT NULL AND due_date IS NULL) OR (due_precision = 'date' AND due_at IS NULL AND due_date IS NOT NULL) OR (due_precision = 'unknown' AND due_at IS NULL AND due_date IS NULL)", name="ck_todos_time_precision"),)
    status: Mapped[TodoStatus] = mapped_column(
        Enum(TodoStatus, name="todo_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=TodoStatus.PENDING, index=True
    )
    source_notification_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("notifications.id"), nullable=True
    )
    # Idempotency key: per-item unique key within a confirmation batch.
    # Format: notif:{notification_id}:user:{user_id}:item:{index}
    # Unique so concurrent confirmations of the same batch cannot duplicate items
    # (race loser gets IntegrityError and returns the winning batch). NULLable and
    # multiple NULLs are allowed, so todos not created from confirmation are unaffected.
    confirmation_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
