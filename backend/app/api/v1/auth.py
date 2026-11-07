"""Auth endpoints: register, login, refresh, logout (SEC-05, SEC-06, SEC-07)."""

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.response import ApiError, success_response
from app.db.session import get_db
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


def _validate_origin(origin: str | None) -> None:
    """Validate Origin for cookie-based write operations (SEC-07)."""
    if origin is not None and origin not in ALLOWED_ORIGINS:
        raise ApiError(code="ACCESS_DENIED", message="invalid origin")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
    )


@router.post("/register")
async def register(
    body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    result = await service.register(body.username, body.password)
    return success_response(
        data=result, message="registered", request_id=request.state.request_id
    )


@router.post("/login")
async def login(
    body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    tokens = await service.login(body.username, body.password)
    refresh_token = tokens.pop("refresh_token")
    resp = JSONResponse(
        content=success_response(
            data=tokens, message="login ok", request_id=request.state.request_id
        )
    )
    _set_refresh_cookie(resp, refresh_token)
    return resp


@router.post("/refresh")
async def refresh(
    request: Request,
    origin: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_origin(origin)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise ApiError(code="AUTH_INVALID", message="no refresh token")
    service = AuthService(db)
    tokens = await service.refresh(refresh_token)
    new_refresh = tokens.pop("refresh_token")
    resp = JSONResponse(
        content=success_response(
            data=tokens, message="refreshed", request_id=request.state.request_id
        )
    )
    _set_refresh_cookie(resp, new_refresh)
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    origin: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    _validate_origin(origin)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        service = AuthService(db)
        await service.logout(refresh_token)
    resp = JSONResponse(
        content=success_response(message="logged out", request_id=request.state.request_id)
    )
    resp.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth")
    return resp


@router.get("/me")
async def me(request: Request, user=Depends(get_current_user)):
    return success_response(
        data={"user_id": user.id, "username": user.username},
        request_id=request.state.request_id,
    )
