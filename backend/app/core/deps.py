"""Authentication dependencies (SEC-05, SEC-06)."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.repositories.auth import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    if credentials is None:
        raise ApiError(code="AUTH_INVALID", message="authentication required")
    payload = decode_access_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise ApiError(code="AUTH_INVALID", message="invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise ApiError(code="AUTH_INVALID", message="invalid token")
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise ApiError(code="AUTH_INVALID", message="user not found")
    return user
