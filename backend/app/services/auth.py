"""Auth business logic: register, login, refresh, logout (SEC-05, SEC-06, SEC-07)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.response import ApiError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.repositories.auth import SessionRepository, UserRepository


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)

    async def register(self, username: str, password: str) -> dict:
        # Validate input at boundary already; business rule: unique username
        existing = await self.user_repo.get_by_username(username)
        if existing:
            # Don't leak whether username exists (SEC-05) - use conflict
            raise ApiError(
                code="CONFLICT_STATE",
                message="registration failed",
            )
        user = await self.user_repo.create(username, hash_password(password))
        return {"user_id": user.id, "username": user.username}

    async def login(self, username: str, password: str) -> dict:
        user = await self.user_repo.get_by_username(username)
        # Generic error to avoid username enumeration (SEC-05)
        if user is None or not verify_password(password, user.password_hash):
            raise ApiError(code="AUTH_INVALID", message="invalid credentials")
        if not user.is_active:
            raise ApiError(code="AUTH_INVALID", message="invalid credentials")

        return await self._issue_tokens(user.id)

    async def refresh(self, refresh_token: str) -> dict:
        token_hash = hash_token(refresh_token)
        session = await self.session_repo.get_by_token_hash(token_hash)
        if session is None or session.is_revoked:
            raise ApiError(code="AUTH_REVOKED", message="session revoked")
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            await self.session_repo.revoke(session.id)
            raise ApiError(code="AUTH_EXPIRED", message="session expired")

        # Rotate: revoke old session, issue new token (SEC-06)
        await self.session_repo.revoke(session.id)
        return await self._issue_tokens(session.user_id)

    async def logout(self, refresh_token: str) -> None:
        token_hash = hash_token(refresh_token)
        session = await self.session_repo.get_by_token_hash(token_hash)
        if session:
            await self.session_repo.revoke(session.id)

    async def _issue_tokens(self, user_id: str) -> dict:
        access_token = create_access_token(user_id)
        refresh_token = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        await self.session_repo.create(
            user_id=user_id,
            refresh_token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
        }
