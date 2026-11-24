"""Tests for tool call record persistence (Task 5): DATA-03, SEC-02/14."""

import pytest
from sqlalchemy import select

from app.models.tool_call_record import ToolCallResult
from app.models.user import User
from app.services.tool_call_record import ToolCallRecordService, serialize


async def _register_login(client, db_session, username: str) -> tuple[dict, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    token = resp.json()["data"]["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    user = (
        await db_session.execute(select(User).where(User.username == username))
    ).scalar_one()
    return auth, user.id


@pytest.mark.asyncio
async def test_write_three_statuses_and_query(client, db_session):
    auth, owner_id = await _register_login(client, db_session, "alice")
    svc = ToolCallRecordService(db_session)
    # Need a server to exist so record_call resolves ownership.
    await client.post(
        "/api/v1/tool-servers",
        json={"name": "search", "base_url": "http://x:8090"},
        headers=auth,
    )
    for i, result in enumerate(
        [ToolCallResult.SUCCESS, ToolCallResult.REJECTED, ToolCallResult.ERROR]
    ):
        rec = await svc.record_call(
            owner_id=owner_id,
            tool_name="unit_convert",
            server_name="search",
            result=result,
            triggered_by=owner_id,
            conversation_id="conv-1",
            round_index=i,
            duration_ms=100 + i,
        )
        assert rec is not None
    resp = await client.get("/api/v1/tool-call-records", headers=auth)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 3
    results = {item["result"] for item in data["items"]}
    assert results == {"success", "rejected", "error"}


@pytest.mark.asyncio
async def test_query_isolated_by_owner(client, db_session):
    auth_a, owner_a = await _register_login(client, db_session, "bob")
    auth_b, _ = await _register_login(client, db_session, "carol")
    await client.post(
        "/api/v1/tool-servers",
        json={"name": "search", "base_url": "http://x:8090"},
        headers=auth_a,
    )
    await ToolCallRecordService(db_session).record_call(
        owner_id=owner_a,
        tool_name="unit_convert",
        server_name="search",
        result=ToolCallResult.SUCCESS,
        triggered_by=owner_a,
    )
    a_resp = await client.get("/api/v1/tool-call-records", headers=auth_a)
    b_resp = await client.get("/api/v1/tool-call-records", headers=auth_b)
    assert a_resp.json()["data"]["total"] == 1
    assert b_resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_no_record_when_server_deleted(client, db_session):
    auth, owner_id = await _register_login(client, db_session, "dave")
    svc = ToolCallRecordService(db_session)
    created = await client.post(
        "/api/v1/tool-servers",
        json={"name": "ephemeral", "base_url": "http://x:8090"},
        headers=auth,
    )
    sid = created.json()["data"]["id"]
    before = await svc.record_call(
        owner_id, "unit_convert", "ephemeral", ToolCallResult.SUCCESS, owner_id
    )
    assert before is not None
    await client.delete(f"/api/v1/tool-servers/{sid}", headers=auth)
    after = await svc.record_call(
        owner_id, "unit_convert", "ephemeral", ToolCallResult.SUCCESS, owner_id
    )
    assert after is None  # server gone -> no record written


@pytest.mark.asyncio
async def test_no_record_when_server_renamed(client, db_session):
    auth, owner_id = await _register_login(client, db_session, "erin")
    svc = ToolCallRecordService(db_session)
    created = await client.post(
        "/api/v1/tool-servers",
        json={"name": "old-name", "base_url": "http://x:8090"},
        headers=auth,
    )
    sid = created.json()["data"]["id"]
    await client.patch(
        f"/api/v1/tool-servers/{sid}", json={"name": "new-name"}, headers=auth
    )
    rec = await svc.record_call(
        owner_id, "unit_convert", "old-name", ToolCallResult.SUCCESS, owner_id
    )
    assert rec is None


@pytest.mark.asyncio
async def test_record_excludes_sensitive_body(client, db_session):
    auth, owner_id = await _register_login(client, db_session, "frank")
    await client.post(
        "/api/v1/tool-servers",
        json={"name": "search", "base_url": "http://x:8090"},
        headers=auth,
    )
    rec = await ToolCallRecordService(db_session).record_call(
        owner_id, "unit_convert", "search", ToolCallResult.SUCCESS, owner_id
    )
    fields = set(serialize(rec).keys())
    # No arguments, no result body, no user question text.
    assert "arguments" not in fields
    assert "result_body" not in fields
    assert "content" not in fields
    assert "raw_text" not in fields


@pytest.mark.asyncio
async def test_page_size_over_max_rejected(client, db_session):
    auth, _ = await _register_login(client, db_session, "grace")
    resp = await client.get(
        "/api/v1/tool-call-records?page_size=999", headers=auth
    )
    assert resp.status_code == 400
