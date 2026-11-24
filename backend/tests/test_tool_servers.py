"""Tests for tool server governance (Task 3): SEC-02/08, BE-04.

Covers: token encryption at rest + never returned, owner isolation (cross-user
404), connect state machine (success replaces list / failure sets error),
disconnect clears the discovered tool list.
"""

import pytest
from sqlalchemy import select

from app.core.crypto import decrypt_secret
from app.models.tool_server import ToolServer
from app.services.mcp_discovery import McpDiscoveryError


async def _register_login(client, username: str) -> dict:
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


PLAIN_TOKEN = "s3cr3t-server-token"


@pytest.mark.asyncio
async def test_register_encrypts_token_and_hides_it(client, db_session):
    auth = await _register_login(client, "alice")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "search", "base_url": "http://x:8090", "token": PLAIN_TOKEN},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # Token plaintext and cipher must never appear in the response.
    body = resp.text
    assert PLAIN_TOKEN not in body
    assert "token_cipher" not in data
    assert data["has_token"] is True
    assert data["status"] == "unconnected"

    row = (
        await db_session.execute(select(ToolServer).where(ToolServer.id == data["id"]))
    ).scalar_one()
    assert row.token_cipher is not None
    assert row.token_cipher != PLAIN_TOKEN
    assert decrypt_secret(row.token_cipher) == PLAIN_TOKEN


@pytest.mark.asyncio
async def test_register_without_token_has_token_false(client):
    auth = await _register_login(client, "bob")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "search", "base_url": "http://x:8090"},
        headers=auth,
    )
    assert resp.json()["data"]["has_token"] is False


@pytest.mark.asyncio
async def test_list_is_isolated_by_owner(client):
    auth_a = await _register_login(client, "carol")
    auth_b = await _register_login(client, "dave")
    for i in range(2):
        await client.post(
            "/api/v1/tool-servers",
            json={"name": f"s{i}", "base_url": "http://x:8090"},
            headers=auth_a,
        )
    await client.post(
        "/api/v1/tool-servers",
        json={"name": "only-b", "base_url": "http://x:8090"},
        headers=auth_b,
    )
    a_list = (await client.get("/api/v1/tool-servers", headers=auth_a)).json()["data"]
    b_list = (await client.get("/api/v1/tool-servers", headers=auth_b)).json()["data"]
    assert len(a_list) == 2
    assert len(b_list) == 1
    assert all(s["name"] != "only-b" for s in a_list)


@pytest.mark.asyncio
async def test_cross_owner_get_returns_404(client):
    auth_a = await _register_login(client, "erin")
    auth_b = await _register_login(client, "frank")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "s", "base_url": "http://x:8090"},
        headers=auth_a,
    )
    sid = resp.json()["data"]["id"]
    # Missing id and other-owner id must be indistinguishable (404).
    missing = await client.get("/api/v1/tool-servers/nope", headers=auth_b)
    other = await client.get(f"/api/v1/tool-servers/{sid}", headers=auth_b)
    assert missing.status_code == 404
    assert other.status_code == 404
    assert other.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_owner_update_and_delete_404(client):
    auth_a = await _register_login(client, "grace")
    auth_b = await _register_login(client, "heidi")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "s", "base_url": "http://x:8090"},
        headers=auth_a,
    )
    sid = resp.json()["data"]["id"]
    up = await client.patch(
        f"/api/v1/tool-servers/{sid}", json={"name": "x"}, headers=auth_b
    )
    dl = await client.delete(f"/api/v1/tool-servers/{sid}", headers=auth_b)
    assert up.status_code == 404
    assert dl.status_code == 404
    # Owner can still see it unchanged.
    own = await client.get(f"/api/v1/tool-servers/{sid}", headers=auth_a)
    assert own.status_code == 200
    assert own.json()["data"]["name"] == "s"


@pytest.mark.asyncio
async def test_connect_success_replaces_tool_list(client, monkeypatch):
    import app.services.tool_server as ts

    async def fake_discover(base_url, token, timeout=10.0):
        return [{"name": "unit_convert", "description": "d", "inputSchema": {}}]

    monkeypatch.setattr(ts, "discover_tools", fake_discover)

    auth = await _register_login(client, "ivan")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "s", "base_url": "http://x:8090", "token": "t"},
        headers=auth,
    )
    sid = resp.json()["data"]["id"]
    conn = await client.post(f"/api/v1/tool-servers/{sid}/connect", headers=auth)
    data = conn.json()["data"]
    assert data["status"] == "connected"
    assert data["last_error"] is None
    assert [t["name"] for t in data["discovered_tools"]] == ["unit_convert"]

    tools = await client.get(f"/api/v1/tool-servers/{sid}/tools", headers=auth)
    assert tools.json()["data"]["tools"][0]["name"] == "unit_convert"


@pytest.mark.asyncio
async def test_connect_failure_sets_error_and_keeps_old_list(client, monkeypatch):
    import app.services.tool_server as ts

    calls = {"n": 0}

    async def fake_discover(base_url, token, timeout=10.0):
        calls["n"] += 1
        if calls["n"] == 1:
            return [{"name": "first", "description": "d", "inputSchema": {}}]
        raise McpDiscoveryError("boom")

    monkeypatch.setattr(ts, "discover_tools", fake_discover)

    auth = await _register_login(client, "judy")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "s", "base_url": "http://x:8090"},
        headers=auth,
    )
    sid = resp.json()["data"]["id"]
    # First connect succeeds, stores ["first"].
    await client.post(f"/api/v1/tool-servers/{sid}/connect", headers=auth)
    # Second connect fails -> error, old list preserved, not doubled.
    conn = await client.post(f"/api/v1/tool-servers/{sid}/connect", headers=auth)
    data = conn.json()["data"]
    assert data["status"] == "error"
    assert data["last_error"] == "boom"
    assert [t["name"] for t in data["discovered_tools"]] == ["first"]


@pytest.mark.asyncio
async def test_disconnect_clears_tool_list(client, monkeypatch):
    import app.services.tool_server as ts

    async def fake_discover(base_url, token, timeout=10.0):
        return [{"name": "unit_convert", "description": "d", "inputSchema": {}}]

    monkeypatch.setattr(ts, "discover_tools", fake_discover)

    auth = await _register_login(client, "karl")
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "s", "base_url": "http://x:8090"},
        headers=auth,
    )
    sid = resp.json()["data"]["id"]
    await client.post(f"/api/v1/tool-servers/{sid}/connect", headers=auth)
    disc = await client.post(
        f"/api/v1/tool-servers/{sid}/disconnect", headers=auth
    )
    data = disc.json()["data"]
    assert data["status"] == "unconnected"
    assert data["discovered_tools"] == []
