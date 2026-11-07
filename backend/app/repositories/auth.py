"""Data access for users and sessions (BE-01, SEC-05)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session as AuthSession
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, username: str, password_hash: str) -> User:
        user = User(username=username, password_hash=password_hash)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, user_id: str, refresh_token_hash: str, expires_at
    ) -> AuthSession:
        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        result = await self.db.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, session_id: str) -> None:
        session = await self.db.get(AuthSession, session_id)
        if session:
            session.is_revoked = True
            await self.db.commit()

    async def revoke_all_for_user(self, user_id: str) -> None:
        result = await self.db.execute(
            select(AuthSession).where(AuthSession.user_id == user_id)
        )
        for session in result.scalars().all():
            session.is_revoked = True
        await self.db.commit()
