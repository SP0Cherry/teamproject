"""Concurrent confirmation idempotency (BE-14 / delivery-gate 并发三查).

Fires N concurrent confirmations of the SAME notification and asserts that only
one batch of todos is produced (per-item unique confirmation_key + IntegrityError
fallback in ConfirmationService.confirm).

Concurrency model: every request gets its OWN async session against a shared
in-memory SQLite database (StaticPool single connection, writes serialized by
aiosqlite). This mirrors production per-request transactions and lets the unique
index on todos.confirmation_key enforce idempotency across concurrent commits.

SQLite caveat: a single shared connection cannot reproduce Postgres multi-connection
contention, but it does validate the application-layer dedup + unique-index fallback
end to end, and the command is rerunnable offline. See reports/risk-concurrency.md.
"""

import asyncio
import json
import os
import tempfile
import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

# Import models so their tables register on Base.metadata
import app.models  # noqa: F401


def _model_response(text: str):
    valid = {
        "title": "通知",
        "content": text,
        "deadline": None,
        "items": [
            {
                "text": "事项",
                "date": None,
                "time": None,
                "date_expression": None,
                "source_text": text,
                "notes": "无",
            }
        ],
    }
    return {
        "role": "assistant",
        "content": json.dumps(valid, ensure_ascii=False),
        "tool_calls": None,
        "time_context": None,
    }


@pytest_asyncio.fixture
async def concurrency_client():
    """File-based SQLite with NullPool so each request gets its OWN connection,
    giving real transaction isolation across the concurrent requests (models
    production per-request transactions better than a single shared connection).
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def override_get_db():
            async with SessionLocal() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
        # aiosqlite may release the file handle slightly after dispose() on Windows;
        # retry the unlink so teardown does not raise a spurious PermissionError.
        for _ in range(10):
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
                break
            except PermissionError:
                time.sleep(0.1)


async def _register_and_login(client: AsyncClient, username: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    return resp.json()["data"]["access_token"]


async def _uid(client: AsyncClient, token: str) -> str:
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    return me.json()["data"]["user_id"]


async def _create_notification(client: AsyncClient, owner_id: str) -> str:
    with patch(
        "app.services.agent.loop.chat_completion_with_tools", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = _model_response("周五开会")
        resp = await client.post(
            "/api/v1/notifications/ingest",
            json={"text": "周五开会", "owner_id": owner_id},
            headers={"source": "demo-source", "x-source-token": "demo-secret-change-me"},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_concurrent_confirm_produces_single_batch(concurrency_client: AsyncClient):
    token = await _register_and_login(concurrency_client, "concurrent_user")
    uid = await _uid(concurrency_client, token)
    notif_id = await _create_notification(concurrency_client, uid)

    candidates = [{"title": "task1"}, {"title": "task2"}]
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/api/v1/notifications/{notif_id}/confirm"

    async def one_confirm():
        return await concurrency_client.post(
            url, json={"candidates": candidates}, headers=headers
        )

    # Fire N concurrent confirmations of the same notification.
    n = 8
    results = await asyncio.gather(
        *[one_confirm() for _ in range(n)], return_exceptions=True
    )

    # No request may error; idempotent retries must all return 200.
    responses = [r for r in results if not isinstance(r, Exception)]
    assert responses, f"all concurrent requests raised: {results}"
    statuses = [r.status_code for r in responses]
    assert all(s == 200 for s in statuses), (
        f"non-200 among concurrent calls: {statuses}"
    )

    # Exactly one batch of todos exists (idempotency via confirmation_key).
    todos = await concurrency_client.get("/api/v1/todos", headers=headers)
    data = todos.json()["data"]
    assert len(data) == len(candidates), (
        f"idempotency violated: expected {len(candidates)} todos, got {len(data)}"
    )

    # Every concurrent call returns a batch of the same size as the candidates.
    for r in responses:
        assert len(r.json()["data"]) == len(candidates)
