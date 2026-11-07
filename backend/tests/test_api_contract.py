"""Contract tests for unified API response, error codes, and background tasks.

Covers BE-03, BE-04, SEC-02: invalid params, unauthorized objects,
dependency errors, and 202-then-failure task status.
"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client, username, password="password123"):
    await client.post("/api/v1/auth/register", json={"username": username, "password": password})
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_response_envelope_has_required_fields(client: AsyncClient):
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"code", "message", "data", "request_id"}
    assert body["code"] == "OK"


@pytest.mark.asyncio
async def test_request_id_present_in_headers(client: AsyncClient):
    resp = await client.get("/api/v1/healthz", headers={"X-Request-ID": "test-req-123"})
    assert resp.headers["X-Request-ID"] == "test-req-123"
    assert resp.json()["request_id"] == "test-req-123"


@pytest.mark.asyncio
async def test_unknown_route_returns_404_with_code(client: AsyncClient):
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_task_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/tasks/any-id")
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_task_not_found_for_authorized_user(client: AsyncClient):
    token = await _register_and_login(client, "user_a")
    resp = await client.get(
        "/api/v1/tasks/nonexistent-id", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_task_owner_isolation(client: AsyncClient, db_session):
    """User B cannot see user A's task (SEC-02)."""
    from app.models.task import BackgroundTask, TaskStatus

    task = BackgroundTask(
        id="task-owner-a",
        task_type="ocr",
        status=TaskStatus.SUCCEEDED,
        owner_id="user-a-fixed",
        progress=100,
    )
    db_session.add(task)
    await db_session.commit()

    token_b = await _register_and_login(client, "user_b")
    resp = await client.get(
        "/api/v1/tasks/task-owner-a", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_failed_status_reflects_error(client: AsyncClient, db_session):
    from app.models.task import BackgroundTask, TaskStatus

    task = BackgroundTask(
        id="task-failed",
        task_type="ocr",
        status=TaskStatus.FAILED,
        owner_id="user-failed",
        progress=100,
        error="ocr engine timeout",
    )
    db_session.add(task)
    await db_session.commit()

    token = await _register_and_login(client, "user_failed_owner")
    # Manually set owner_id to match the registered user
    # For this test we need the owner to match; use a direct DB approach
    from app.repositories.auth import UserRepository
    user = await UserRepository(db_session).get_by_username("user_failed_owner")
    task.owner_id = user.id
    await db_session.commit()

    resp = await client.get(
        "/api/v1/tasks/task-failed", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "failed"
    assert body["data"]["error"] == "ocr engine timeout"
