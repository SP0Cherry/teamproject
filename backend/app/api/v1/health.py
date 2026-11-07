from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success_response
from app.db.session import get_db

router = APIRouter()


@router.get("/healthz")
async def liveness(request: Request) -> dict:
    """Liveness probe: process is alive."""
    return success_response(data={"status": "alive"}, request_id=request.state.request_id)


@router.get("/readyz")
async def readiness(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness probe: required dependencies are reachable."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        from app.core.response import ApiError

        raise ApiError(
            code="DEPENDENCY_UNAVAILABLE",
            message="database unavailable",
        )
    return success_response(
        data={"status": "ready", "db": "ok"},
        request_id=request.state.request_id,
    )
