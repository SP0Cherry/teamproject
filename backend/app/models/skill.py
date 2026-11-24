import enum
import uuid

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SkillCapability(str, enum.Enum):
    QA = "qa"
    NOTIFICATION_EXTRACTION = "notification_extraction"


class Skill(Base, TimestampMixin):
    """技能配置：在某能力场景下绑定若干 `tool@server` 引用（保存前校验）。"""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[SkillCapability] = mapped_column(
        Enum(
            SkillCapability,
            name="_skills_capability",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    tool_refs: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
