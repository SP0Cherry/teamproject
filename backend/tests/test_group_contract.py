"""Contract tests for group list/detail/member fields (BE-01, SEC-02)."""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, username: str) -> str:
    await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "password123"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password123"}
    )
    return resp.json()["data"]["access_token"]


async def _create_group(client: AsyncClient, token: str, name: str, desc: str | None = None):
    payload = {"name": name}
    if desc is not None:
        payload["description"] = desc
    resp = await client.post(
        "/api/v1/groups", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    data = resp.json()["data"]
    return data["id"], data["invite_token"]


@pytest.mark.asyncio
async def test_member_list_returns_username_and_joined_at(client: AsyncClient):
    token_a = await _register_and_login(client, "ct_a")
    token_b = await _register_and_login(client, "ct_b")
    gid, invite = await _create_group(client, token_a, "ct-g1", "描述A")

    await client.post(
        "/api/v1/groups/join-by-token",
        json={"invite_token": invite},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    resp = await client.get(
        f"/api/v1/groups/{gid}/members",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    members = resp.json()["data"]
    assert len(members) == 2
    for m in members:
        assert "user_id" in m
        assert "username" in m and m["username"]
        assert m["role"] in ("owner", "admin", "member")
        assert "joined_at" in m and m["joined_at"]
    usernames = {m["username"] for m in members}
    assert usernames == {"ct_a", "ct_b"}


@pytest.mark.asyncio
async def test_non_member_cannot_list_members(client: AsyncClient):
    token_a = await _register_and_login(client, "ct_c")
    token_out = await _register_and_login(client, "ct_out")
    gid, _ = await _create_group(client, token_a, "ct-g2")

    resp = await client.get(
        f"/api/v1/groups/{gid}/members",
        headers={"Authorization": f"Bearer {token_out}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_group_detail_returns_my_role_and_sync(client: AsyncClient):
    token_a = await _register_and_login(client, "ct_d")
    gid, _ = await _create_group(client, token_a, "ct-g3")

    resp = await client.get(
        f"/api/v1/groups/{gid}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["my_role"] == "owner"
    assert data["my_sync_enabled"] is False
    assert "invite_token" in data


@pytest.mark.asyncio
async def test_group_list_returns_aggregated_fields(client: AsyncClient):
    token_a = await _register_and_login(client, "ct_e")
    token_b = await _register_and_login(client, "ct_f")
    gid, invite = await _create_group(client, token_a, "ct-g4", "列表描述")

    await client.post(
        "/api/v1/groups/join-by-token",
        json={"invite_token": invite},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    resp = await client.get(
        "/api/v1/groups", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 200
    groups = resp.json()["data"]
    assert len(groups) == 1
    g = groups[0]
    assert g["id"] == gid
    assert g["name"] == "ct-g4"
    assert g["description"] == "列表描述"
    assert g["my_role"] == "owner"
    assert g["my_sync_enabled"] is False
    assert g["member_count"] == 2
