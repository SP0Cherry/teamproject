"""Auth tests: register, login, refresh rotation, logout, authorization.

Covers SEC-05, SEC-06, SEC-07, account-access spec.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == "OK"

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_duplicate_registration_fails(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "password": "password123"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CONFLICT_STATE"


@pytest.mark.asyncio
async def test_wrong_credentials_fails(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "carol", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_login_unknown_user_does_not_leak_existence(client: AsyncClient):
    """Error for unknown user must match wrong password (SEC-05)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "ghost", "password": "whatever"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "dave", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "dave", "password": "password123"},
    )
    cookies = resp.cookies
    assert "refresh_token" in cookies

    # Refresh should rotate and return new access token
    resp2 = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()["data"]

    # Old refresh token should now be revoked
    resp3 = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert resp3.status_code == 401
    assert resp3.json()["code"] == "AUTH_REVOKED"


@pytest.mark.asyncio
async def test_logout_revokes_session(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "eve", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "eve", "password": "password123"},
    )
    cookies = resp.cookies

    await client.post("/api/v1/auth/logout", cookies=cookies)
    resp2 = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert resp2.status_code == 401
    assert resp2.json()["code"] == "AUTH_REVOKED"


@pytest.mark.asyncio
async def test_anonymous_cannot_access_protected(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_access_token_can_access_me(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"username": "frank", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "frank", "password": "password123"},
    )
    token = resp.json()["data"]["access_token"]
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "frank"


@pytest.mark.asyncio
async def test_password_too_short_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "gina", "password": "short"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


@pytest.mark.asyncio
async def test_bad_origin_rejected_on_refresh(client: AsyncClient):
    """Cookie-based writes must validate Origin (SEC-07)."""
    await client.post(
        "/api/v1/auth/register",
        json={"username": "hank", "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "hank", "password": "password123"},
    )
    cookies = resp.cookies
    resp = await client.post(
        "/api/v1/auth/refresh",
        cookies=cookies,
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCESS_DENIED"
