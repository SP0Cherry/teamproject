"""Tests for skill pre-save three-way validation (Task 4): AI-09, SEC-02/11."""

import pytest


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


async def _connected_server(client, auth, name, tool_names, monkeypatch) -> str:
    import app.services.tool_server as ts

    async def fake(base_url, token, timeout=10.0):
        return [
            {"name": n, "description": "d", "inputSchema": {"type": "object"}}
            for n in tool_names
        ]

    monkeypatch.setattr(ts, "discover_tools", fake)
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": name, "base_url": "http://x:8090"},
        headers=auth,
    )
    sid = resp.json()["data"]["id"]
    await client.post(f"/api/v1/tool-servers/{sid}/connect", headers=auth)
    return sid


@pytest.mark.asyncio
async def test_create_skill_with_valid_refs(client, monkeypatch):
    auth = await _register_login(client, "alice")
    await _connected_server(client, auth, "search", ["unit_convert"], monkeypatch)
    resp = await client.post(
        "/api/v1/skills",
        json={
            "name": "qa-with-tools",
            "capability": "qa",
            "tool_refs": ["unit_convert@search"],
        },
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["tool_refs"] == ["unit_convert@search"]
    assert data["capability"] == "qa"


@pytest.mark.asyncio
async def test_empty_tool_refs_allowed(client):
    auth = await _register_login(client, "bob")
    resp = await client.post(
        "/api/v1/skills",
        json={"name": "plain", "capability": "qa", "tool_refs": []},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["tool_refs"] == []


@pytest.mark.asyncio
async def test_reject_bad_ref_format(client, monkeypatch):
    auth = await _register_login(client, "carol")
    await _connected_server(client, auth, "search", ["unit_convert"], monkeypatch)
    for bad in ["BadRef", "unit_convert@", "@search", "unit convert@search", "UPPER@search"]:
        resp = await client.post(
            "/api/v1/skills",
            json={"name": "s", "capability": "qa", "tool_refs": [bad]},
            headers=auth,
        )
        assert resp.status_code == 422, bad
        assert resp.json()["code"] == "BUSINESS_RULE", bad


@pytest.mark.asyncio
async def test_reject_server_not_connected(client):
    auth = await _register_login(client, "dave")
    # Register a server but do NOT connect it.
    resp = await client.post(
        "/api/v1/tool-servers",
        json={"name": "idle", "base_url": "http://x:8090"},
        headers=auth,
    )
    resp = await client.post(
        "/api/v1/skills",
        json={"name": "s", "capability": "qa", "tool_refs": ["unit_convert@idle"]},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "BUSINESS_RULE"


@pytest.mark.asyncio
async def test_reject_tool_not_in_list(client, monkeypatch):
    auth = await _register_login(client, "erin")
    await _connected_server(client, auth, "search", ["unit_convert"], monkeypatch)
    resp = await client.post(
        "/api/v1/skills",
        json={"name": "s", "capability": "qa", "tool_refs": ["nonexistent@search"]},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "BUSINESS_RULE"


@pytest.mark.asyncio
async def test_reject_other_owner_server(client, monkeypatch):
    auth_b = await _register_login(client, "frank")
    await _connected_server(client, auth_b, "shared", ["unit_convert"], monkeypatch)
    auth_a = await _register_login(client, "grace")
    resp = await client.post(
        "/api/v1/skills",
        json={"name": "s", "capability": "qa", "tool_refs": ["unit_convert@shared"]},
        headers=auth_a,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "BUSINESS_RULE"


@pytest.mark.asyncio
async def test_update_runs_validation(client, monkeypatch):
    auth = await _register_login(client, "heidi")
    await _connected_server(client, auth, "search", ["unit_convert"], monkeypatch)
    created = await client.post(
        "/api/v1/skills",
        json={"name": "s", "capability": "qa", "tool_refs": ["unit_convert@search"]},
        headers=auth,
    )
    sid = created.json()["data"]["id"]
    # Update to an invalid reference must be rejected.
    resp = await client.patch(
        f"/api/v1/skills/{sid}",
        json={"tool_refs": ["evil_tool@search"]},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "BUSINESS_RULE"


@pytest.mark.asyncio
async def test_cross_owner_skill_404(client, monkeypatch):
    auth_a = await _register_login(client, "ivan")
    auth_b = await _register_login(client, "judy")
    await _connected_server(client, auth_a, "search", ["unit_convert"], monkeypatch)
    created = await client.post(
        "/api/v1/skills",
        json={"name": "s", "capability": "qa", "tool_refs": ["unit_convert@search"]},
        headers=auth_a,
    )
    sid = created.json()["data"]["id"]
    get_b = await client.get(f"/api/v1/skills/{sid}", headers=auth_b)
    patch_b = await client.patch(f"/api/v1/skills/{sid}", json={"name": "x"}, headers=auth_b)
    delete_b = await client.delete(f"/api/v1/skills/{sid}", headers=auth_b)
    assert get_b.status_code == 404
    assert patch_b.status_code == 404
    assert delete_b.status_code == 404
