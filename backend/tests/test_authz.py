"""Authorization tests for groups and unified access rules (SEC-02, SEC-03)."""

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


@pytest.mark.asyncio
async def test_create_group_makes_owner_member(client: AsyncClient):
    token = await _register_and_login(client, "group_owner")
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Team A", "description": "test group"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    group_id = resp.json()["data"]["id"]

    # Owner can view the group
    resp = await client.get(
        f"/api/v1/groups/{group_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Team A"

    # Owner sees group in list
    resp = await client.get(
        "/api/v1/groups", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert any(g["id"] == group_id for g in resp.json()["data"])


@pytest.mark.asyncio
async def test_non_member_cannot_view_group(client: AsyncClient):
    token_owner = await _register_and_login(client, "owner_a")
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Private Group"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    group_id = resp.json()["data"]["id"]

    token_other = await _register_and_login(client, "outsider")
    resp = await client.get(
        f"/api/v1/groups/{group_id}",
        headers={"Authorization": f"Bearer {token_other}"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCESS_DENIED"


@pytest.mark.asyncio
async def test_user_can_join_and_then_view_group(client: AsyncClient):
    token_owner = await _register_and_login(client, "owner_b")
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Joinable Group"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    group_id = resp.json()["data"]["id"]

    token_newbie = await _register_and_login(client, "newbie")
    # Before joining: cannot view
    resp = await client.get(
        f"/api/v1/groups/{group_id}",
        headers={"Authorization": f"Bearer {token_newbie}"},
    )
    assert resp.status_code == 403

    # Join
    resp = await client.post(
        f"/api/v1/groups/{group_id}/join",
        headers={"Authorization": f"Bearer {token_newbie}"},
    )
    assert resp.status_code == 200

    # After joining: can view
    resp = await client.get(
        f"/api/v1/groups/{group_id}",
        headers={"Authorization": f"Bearer {token_newbie}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Joinable Group"


@pytest.mark.asyncio
async def test_groups_list_only_returns_user_groups(client: AsyncClient):
    token_a = await _register_and_login(client, "user_a")
    token_b = await _register_and_login(client, "user_b")

    await client.post(
        "/api/v1/groups",
        json={"name": "A's Group"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp = await client.get(
        "/api/v1/groups", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_authz_service_personal_owner(db_session):
    from app.core.response import ApiError
    from app.services.authz import AuthzService

    svc = AuthzService(db_session)
    await svc.require_personal_owner("u1", "u1")  # owner matches -> no raise
    with pytest.raises(ApiError) as ei:
        await svc.require_personal_owner("u1", "u2")
    assert ei.value.code == "ACCESS_DENIED"


@pytest.mark.asyncio
async def test_authz_service_group_roles(db_session):
    from app.core.response import ApiError
    from app.core.security import hash_password
    from app.models.group import GroupRole
    from app.models.user import User
    from app.repositories.group import GroupRepository
    from app.services.authz import AuthzService

    for uid in ("owner", "admin", "member"):
        db_session.add(User(id=uid, username=uid, password_hash=hash_password("x")))
    await db_session.commit()

    repo = GroupRepository(db_session)
    g = await repo.create("g", None, owner_id="owner")
    await repo.add_member(g.id, "admin", GroupRole.ADMIN)
    await repo.add_member(g.id, "member", GroupRole.MEMBER)
    svc = AuthzService(db_session)

    await svc.require_group_member(g.id, "owner")
    with pytest.raises(ApiError) as ei:
        await svc.require_group_member(g.id, "outsider")
    assert ei.value.code == "ACCESS_DENIED"

    await svc.require_group_admin(g.id, "owner")  # OWNER ok
    await svc.require_group_admin(g.id, "admin")  # ADMIN ok
    with pytest.raises(ApiError) as ei:
        await svc.require_group_admin(g.id, "member")
    assert ei.value.code == "ACCESS_DENIED"
    with pytest.raises(ApiError) as ei:
        await svc.require_group_admin(g.id, "outsider")
    assert ei.value.code == "ACCESS_DENIED"
