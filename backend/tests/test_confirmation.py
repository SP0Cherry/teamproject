"""Tests for notification confirmation, idempotency, and todo ops (BE-14, AI-06)."""

import json

import pytest
from httpx import AsyncClient


async def _register_and_login(client, username):
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    return resp.json()["data"]["access_token"]


async def _create_notification(client, owner_id=None):
    """Use source ingest to create a notification, return its id."""
    if owner_id is None:
        # Register a user first
        await client.post(
            "/api/v1/auth/register",
            json={"username": "notif_owner", "password": "password123"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "notif_owner", "password": "password123"},
        )
        # We need the user id; use /me
        token = login.json()["data"]["access_token"]
        me = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        owner_id = me.json()["data"]["user_id"]

    resp = await client.post(
        "/api/v1/notifications/ingest",
        json={"text": "周五开会", "owner_id": owner_id},
        headers={"source": "demo-source", "x-source-token": "demo-secret-change-me"},
    )
    return resp.json()["data"]["id"], owner_id


@pytest.mark.asyncio
async def test_confirm_creates_todos(client: AsyncClient):
    notif_id, owner_id = await _create_notification(client)
    token = await _register_and_login(client, "confirmer")

    # Need to use the same user as owner_id for ownership
    # Re-create notification with the logged-in user
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    uid = me.json()["data"]["user_id"]
    notif_id, _ = await _create_notification(client, owner_id=uid)

    resp = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": [{"title": "开会", "deadline": None}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "开会"


@pytest.mark.asyncio
async def test_confirm_is_idempotent(client: AsyncClient):
    """Repeated confirmation of the same notification produces one batch."""
    token = await _register_and_login(client, "idempotent_user")
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    uid = me.json()["data"]["user_id"]
    notif_id, _ = await _create_notification(client, owner_id=uid)

    candidates = [{"title": "task1"}, {"title": "task2"}]

    # First confirmation
    r1 = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": candidates},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    first_batch = r1.json()["data"]

    # Second confirmation (retry) - should return same batch, not create more
    r2 = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": candidates},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    second_batch = r2.json()["data"]

    # Same number of todos
    assert len(first_batch) == len(second_batch) == 2

    # Total todos in list should be 2, not 4
    todos = await client.get(
        "/api/v1/todos", headers={"Authorization": f"Bearer {token}"}
    )
    assert len(todos.json()["data"]) == 2


@pytest.mark.asyncio
async def test_confirm_empty_candidates_rejected(client: AsyncClient):
    token = await _register_and_login(client, "empty_cand")
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    uid = me.json()["data"]["user_id"]
    notif_id, _ = await _create_notification(client, owner_id=uid)

    resp = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


@pytest.mark.asyncio
async def test_confirm_candidate_without_title_rejected(client: AsyncClient):
    token = await _register_and_login(client, "no_title")
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    uid = me.json()["data"]["user_id"]
    notif_id, _ = await _create_notification(client, owner_id=uid)

    resp = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": [{"description": "no title here"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"

    # Verify no todos were created (no partial batch)
    todos = await client.get(
        "/api/v1/todos", headers={"Authorization": f"Bearer {token}"}
    )
    assert todos.json()["data"] == []


@pytest.mark.asyncio
async def test_todo_complete_and_restore(client: AsyncClient):
    token = await _register_and_login(client, "todo_user")
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    uid = me.json()["data"]["user_id"]
    notif_id, _ = await _create_notification(client, owner_id=uid)

    resp = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": [{"title": "do this"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = resp.json()["data"][0]["id"]

    # Complete
    resp = await client.post(
        f"/api/v1/todos/{todo_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["data"]["status"] == "done"

    # Restore
    resp = await client.post(
        f"/api/v1/todos/{todo_id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["data"]["status"] == "pending"


@pytest.mark.asyncio
async def test_todo_owner_isolation(client: AsyncClient):
    token_a = await _register_and_login(client, "todo_a")
    token_b = await _register_and_login(client, "todo_b")
    me_a = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"}
    )
    uid_a = me_a.json()["data"]["user_id"]
    notif_id, _ = await _create_notification(client, owner_id=uid_a)

    resp = await client.post(
        f"/api/v1/notifications/{notif_id}/confirm",
        json={"candidates": [{"title": "a's task"}]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = resp.json()["data"][0]["id"]

    # User B cannot complete user A's todo
    resp = await client.post(
        f"/api/v1/todos/{todo_id}/complete",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
