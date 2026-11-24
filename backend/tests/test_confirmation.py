"""Tests for notification confirmation, idempotency, and todo ops (BE-14, AI-06)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


def _model_response(text: str):
    """Deterministic model double for notification extraction (no real LLM)."""
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

    with patch(
        "app.services.agent.loop.chat_completion_with_tools", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = _model_response("周五开会")
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


@pytest.mark.asyncio
async def test_confirmation_service_branches(db_session):
    from sqlalchemy.exc import IntegrityError

    from app.core.response import ApiError
    from app.models.group import GroupRole
    from app.models.notification import NotificationStatus
    from app.repositories.group import GroupRepository
    from app.repositories.notification import NotificationRepository
    from app.repositories.todo import TodoRepository
    from app.services.confirmation import ConfirmationService

    notif_repo = NotificationRepository(db_session)
    todo_repo = TodoRepository(db_session)
    group_repo = GroupRepository(db_session)
    svc = ConfirmationService(db_session)
    candidate = {"title": "do something", "deadline": None}

    # personal notification owned by "owner"
    notif = await notif_repo.create(
        owner_id="owner", group_id=None, source="manual", raw_text="hi", parsed="[]"
    )

    # L40-41: confirm nonexistent notification
    with pytest.raises(ApiError) as ei:
        await svc.confirm("nope", "owner", [candidate])
    assert ei.value.code == "RESOURCE_NOT_FOUND"

    # L48-49: personal notification, other user -> not found
    with pytest.raises(ApiError) as ei:
        await svc.confirm(notif.id, "stranger", [candidate])
    assert ei.value.code == "RESOURCE_NOT_FOUND"

    # L44-47: published group notification, non-member -> not found
    g = await group_repo.create("g", None, owner_id="admin")
    g_notif = await notif_repo.create(
        owner_id="admin", group_id=g.id, source="group", raw_text="g hi", parsed="[]"
    )
    g_notif.published = True
    await db_session.commit()
    with pytest.raises(ApiError) as ei:
        await svc.confirm(g_notif.id, "stranger", [candidate])
    assert ei.value.code == "RESOURCE_NOT_FOUND"

    # L63-64: empty candidates rejected
    with pytest.raises(ApiError) as ei:
        await svc.confirm(notif.id, "owner", [])
    assert ei.value.code == "PARAM_INVALID"

    # L58-60: idempotent re-confirm returns the existing batch
    batch = await svc.confirm(
        notif.id, "owner", [candidate, {"title": "two", "deadline": None}]
    )
    again = await svc.confirm(
        notif.id, "owner", [candidate, {"title": "two", "deadline": None}]
    )
    assert len(batch) == 2 and len(again) == 2
    assert {t["id"] for t in batch} == {t["id"] for t in again}

    # L84-89: IntegrityError rollback returns the winning batch.
    # A concurrent racer inserts the winning todo mid-create (after the top idempotency
    # check passed) and commits; then our insert raises IntegrityError. The service rolls
    # back its own partial insert and returns the batch that won the race.
    notif2 = await notif_repo.create(
        owner_id="owner", group_id=None, source="manual", raw_text="race", parsed="[]"
    )
    winner_prefix = f"notif:{notif2.id}:user:owner"
    original_create = todo_repo.create

    async def _racing_create(**kwargs):
        await original_create(
            owner_id="owner",
            title="winner",
            confirmation_key=f"{winner_prefix}:item:0",
        )
        await db_session.commit()
        raise IntegrityError("INSERT INTO todos", {}, Exception("dup key"))

    svc2 = ConfirmationService(db_session)
    svc2.todo_repo.create = _racing_create
    result = await svc2.confirm(notif2.id, "owner", [candidate])
    assert len(result) == 1
    assert result[0]["title"] == "winner"

    # discard branches
    with pytest.raises(ApiError) as ei:
        await svc.discard("nope", "owner")
    assert ei.value.code == "RESOURCE_NOT_FOUND"

    with pytest.raises(ApiError) as ei:
        await svc.discard(notif.id, "stranger")
    assert ei.value.code == "RESOURCE_NOT_FOUND"

    await group_repo.add_member(g.id, "member", GroupRole.MEMBER)
    with pytest.raises(ApiError) as ei:
        await svc.discard(g_notif.id, "member")
    assert ei.value.code == "RESOURCE_NOT_FOUND"

    await svc.discard(notif.id, "owner")
    refreshed = await notif_repo.get(notif.id)
    assert refreshed.status == NotificationStatus.DISCARDED
