"""Auth tests: register, login, refresh rotation, logout, authorization.

Covers SEC-05, SEC-06, SEC-07, account-access spec.
"""

import pytest
from httpx import AsyncClient

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings


def _access_token(user_id: str, *, expired: bool = False) -> str:
    exp = datetime.now(timezone.utc) + (
        timedelta(seconds=-1) if expired else timedelta(minutes=5)
    )
    return jwt.encode(
        {"sub": user_id, "exp": exp, "type": "access"},
        settings.secret_key,
        algorithm="HS256",
    )


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


@pytest.mark.asyncio
async def test_expired_access_token_reports_expired(client: AsyncClient):
    """An expired token must be distinguishable from an invalid one (SEC-05)."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "ivy", "password": "password123"},
    )
    user_id = resp.json()["data"]["user_id"]
    token = _access_token(user_id, expired=True)
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_EXPIRED"


@pytest.mark.asyncio
async def test_malformed_access_token_reports_invalid(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "jack", "password": "password123"},
    )
    user_id = resp.json()["data"]["user_id"]

    # Not a JWT at all
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"

    # Valid structure but tampered signature
    valid = _access_token(user_id)
    tampered = valid[:-1] + ("a" if valid[-1] != "a" else "b")
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_auth_service_register_login_branches(db_session):
    from app.core.response import ApiError
    from app.services.auth import AuthService

    svc = AuthService(db_session)
    reg = await svc.register("alice_svc", "password123")
    assert reg["username"] == "alice_svc"

    with pytest.raises(ApiError) as ei:
        await svc.register("alice_svc", "other")
    assert ei.value.code == "CONFLICT_STATE"

    tokens = await svc.login("alice_svc", "password123")
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]

    with pytest.raises(ApiError) as ei:
        await svc.login("alice_svc", "wrong")
    assert ei.value.code == "AUTH_INVALID"

    with pytest.raises(ApiError) as ei:
        await svc.login("ghost_svc", "x")
    assert ei.value.code == "AUTH_INVALID"

    # inactive user cannot log in
    user = await svc.user_repo.get_by_username("alice_svc")
    user.is_active = False
    await db_session.commit()
    with pytest.raises(ApiError) as ei:
        await svc.login("alice_svc", "password123")
    assert ei.value.code == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_auth_service_refresh_logout_branches(db_session):
    from datetime import datetime, timedelta, timezone

    from app.core.response import ApiError
    from app.core.security import generate_refresh_token, hash_token
    from app.repositories.auth import SessionRepository
    from app.services.auth import AuthService

    svc = AuthService(db_session)
    await svc.register("bob_svc", "password123")
    user = await svc.user_repo.get_by_username("bob_svc")
    sessions = SessionRepository(db_session)

    def _make_session(token, expires_delta):
        return sessions.create(
            user_id=user.id,
            refresh_token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + expires_delta,
        )

    # happy refresh rotates the token; old one becomes revoked
    rt = generate_refresh_token()
    await _make_session(rt, timedelta(days=1))
    new_tokens = await svc.refresh(rt)
    assert new_tokens["access_token"]
    with pytest.raises(ApiError) as ei:
        await svc.refresh(rt)
    assert ei.value.code == "AUTH_REVOKED"

    # unknown token hash -> AUTH_REVOKED
    with pytest.raises(ApiError) as ei:
        await svc.refresh(generate_refresh_token())
    assert ei.value.code == "AUTH_REVOKED"

    # expired session -> AUTH_EXPIRED (and gets revoked)
    rt2 = generate_refresh_token()
    await _make_session(rt2, -timedelta(seconds=1))
    with pytest.raises(ApiError) as ei:
        await svc.refresh(rt2)
    assert ei.value.code == "AUTH_EXPIRED"

    # logout revokes an existing session
    rt3 = generate_refresh_token()
    await _make_session(rt3, timedelta(days=1))
    await svc.logout(rt3)
    with pytest.raises(ApiError) as ei:
        await svc.refresh(rt3)
    assert ei.value.code == "AUTH_REVOKED"
