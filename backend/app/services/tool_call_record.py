"""Tool call record persistence and query (DATA-03, SEC-02/14).

Records are written by the agent runtime (Task 6), never via a public write
endpoint. If the referenced server has been deleted or renamed at call time,
no record is written (spec: 服务器删除不写记录). Records store metadata only.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call_record import ToolCallRecord, ToolCallResult
from app.repositories.tool_call_record import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ToolCallRecordRepository,
)
from app.repositories.tool_server import ToolServerRepository


def serialize(record: ToolCallRecord) -> dict:
    return {
        "id": record.id,
        "tool_name": record.tool_name,
        "server_name": record.server_name,
        "server_id": record.server_id,
        "result": record.result.value,
        "conversation_id": record.conversation_id,
        "round_index": record.round_index,
        "triggered_by": record.triggered_by,
        "duration_ms": record.duration_ms,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


class ToolCallRecordService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ToolCallRecordRepository(db)
        self.server_repo = ToolServerRepository(db)

    async def record_call(
        self,
        owner_id: str,
        tool_name: str,
        server_name: str | None,
        result: ToolCallResult,
        triggered_by: str,
        conversation_id: str | None = None,
        round_index: int | None = None,
        duration_ms: int | None = None,
    ) -> ToolCallRecord | None:
        if not server_name:
            return None
        server = await self.server_repo.find_by_name(owner_id, server_name)
        if server is None:
            # Server deleted or renamed -> do not write a record (spec).
            return None
        return await self.repo.create(
            owner_id=owner_id,
            tool_name=tool_name,
            server_name=server.name,
            server_id=server.id,
            result=result,
            conversation_id=conversation_id,
            round_index=round_index,
            triggered_by=triggered_by,
            duration_ms=duration_ms,
        )

    async def list(
        self, owner_id: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ):
        return await self.repo.list_for_owner(owner_id, page, page_size)


__all__ = ["DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE"]
