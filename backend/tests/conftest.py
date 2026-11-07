"""Test fixtures: isolated DB, file dir, clock, external doubles (TEST-04, TEST-05)."""

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

# Import models so their tables register on Base.metadata
import app.models  # noqa: F401


@pytest.fixture
def test_upload_dir(tmp_path):
    """Isolated private file directory for tests (TEST-04)."""
    d = tmp_path / "uploads"
    d.mkdir()
    return str(d)


@pytest.fixture
def controllable_clock():
    """Injectable clock for time-dependent tests (TEST-05)."""
    state = {"now": datetime(2026, 1, 1, 0, 0, 0)}

    class Clock:
        @staticmethod
        def now():
            return state["now"]

        @staticmethod
        def set(dt):
            state["now"] = dt

    return Clock


@pytest.fixture
def model_double():
    """External model dependency double (TEST-05)."""
    mock = MagicMock()
    mock.return_value = {"items": []}
    return mock


@pytest.fixture
def ocr_double():
    """External OCR dependency double (TEST-05)."""
    mock = MagicMock()
    return mock


@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite async engine for isolated tests (TEST-04)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Async session bound to the test engine."""
    SessionLocal = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """Async test client with DB dependency overridden."""

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
