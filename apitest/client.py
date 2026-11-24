"""Shared HTTP client for apitest: login, Bearer token, request id, SSE parse.

Talks to the in-process FastAPI app through httpx ASGITransport (exercises the
full stack: middleware, request-id, exception handlers, SSE streaming) without
needing a live TCP socket for the backend (TEST-04/06).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from httpx import ASGITransport, AsyncClient


@dataclass
class HttpResponse:
    status: int
    code: str
    data: object
    raw: dict
    request_id: str

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.code in ("SUCCESS", "OK", "0", "")


@dataclass
class SseFrame:
    event: str
    data: dict


@dataclass
class SseStream:
    status: int
    frames: list[SseFrame] = field(default_factory=list)


class ApiClient:
    def __init__(self, app, base_url: str = "http://test") -> None:
        self._transport = ASGITransport(app=app)
        self._client = AsyncClient(transport=self._transport, base_url=base_url, timeout=30.0)
        self._token: str | None = None
        self._seq = 0

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict:
        self._seq += 1
        h = {"X-Request-Id": f"apitest-{self._seq:04d}"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    @staticmethod
    def _envelope(resp) -> HttpResponse:
        try:
            body = resp.json()
        except Exception:
            body = {}
        return HttpResponse(
            status=resp.status_code,
            code=str(body.get("code", "")),
            data=body.get("data"),
            raw=body,
            request_id=str(body.get("request_id", "")),
        )

    async def register(self, username: str, password: str) -> HttpResponse:
        r = await self._client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": password},
            headers=self._headers(),
        )
        return self._envelope(r)

    async def login(self, username: str, password: str) -> HttpResponse:
        r = await self._client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=self._headers(),
        )
        env = self._envelope(r)
        if env.status == 200 and isinstance(env.data, dict):
            self._token = env.data.get("access_token") or self._token
        return env

    async def me(self) -> HttpResponse:
        r = await self._client.get("/api/v1/auth/me", headers=self._headers())
        return self._envelope(r)

    async def get(self, path: str, params: dict | None = None) -> HttpResponse:
        r = await self._client.get(path, params=params or {}, headers=self._headers())
        return self._envelope(r)

    async def post(self, path: str, json_body: dict | None = None) -> HttpResponse:
        r = await self._client.post(path, json=json_body or {}, headers=self._headers())
        return self._envelope(r)

    async def patch(self, path: str, json_body: dict | None = None) -> HttpResponse:
        r = await self._client.patch(path, json=json_body or {}, headers=self._headers())
        return self._envelope(r)

    async def delete(self, path: str) -> HttpResponse:
        r = await self._client.delete(path, headers=self._headers())
        return self._envelope(r)

    async def sse(self, path: str, json_body: dict) -> SseStream:
        """POST and collect all SSE frames until the stream closes."""
        stream = SseStream(status=0)
        started = time.monotonic()
        async with self._client.stream(
            "POST", path, json=json_body, headers=self._headers(), timeout=30.0
        ) as resp:
            stream.status = resp.status_code
            event = "message"
            data_lines: list[str] = []
            async for raw in resp.aiter_lines():
                line = raw.rstrip("\n")
                if line == "":
                    if data_lines:
                        try:
                            payload = json.loads("\n".join(data_lines))
                        except json.JSONDecodeError:
                            payload = {"_raw": "\n".join(data_lines)}
                        stream.frames.append(SseFrame(event=event, data=payload))
                    event = "message"
                    data_lines = []
                    continue
                if line.startswith("event:"):
                    event = line[len("event:"):].strip() or "message"
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].lstrip())
            if data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    payload = {"_raw": "\n".join(data_lines)}
                stream.frames.append(SseFrame(event=event, data=payload))
        stream.elapsed_ms = round((time.monotonic() - started) * 1000)  # type: ignore[attr-defined]
        return stream
