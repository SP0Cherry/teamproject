"""Append-only data access for tool_call_records (DATA-03, BE-09).

Only insert and owner-scoped paginated select are exposed; there is no
update or delete path. Sensitive bodies (arguments, results) are never stored.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call_record import ToolCallRecord, ToolCallResult

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class ToolCallRecordRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        owner_id: str,
        tool_name: str,
        server_name: str | None,
        server_id: str | None,
        result: ToolCallResult,
        conversation_id: str | None,
        round_index: int | None,
        triggered_by: str,
        duration_ms: int | None,
    ) -> ToolCallRecord:
        record = ToolCallRecord(
            owner_id=owner_id,
            tool_name=tool_name,
            server_name=server_name,
            server_id=server_id,
            result=result,
            conversation_id=conversation_id,
            round_index=round_index,
            triggered_by=triggered_by,
            duration_ms=duration_ms,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def list_for_owner(
        self, owner_id: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> tuple[list[ToolCallRecord], int]:
        page = max(1, page)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        total = (
            await self.db.execute(
                select(func.count(ToolCallRecord.id)).where(
                    ToolCallRecord.owner_id == owner_id
                )
            )
        ).scalar() or 0
        result = await self.db.execute(
            select(ToolCallRecord)
            .where(ToolCallRecord.owner_id == owner_id)
            .order_by(ToolCallRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
