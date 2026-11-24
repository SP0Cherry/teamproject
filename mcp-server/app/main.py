"""FastAPI entrypoint exposing GET /health and POST /mcp (JSON-RPC 2.0)."""

import json
import os

import anyio
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from . import jsonrpc
from .tools import call_tool, list_tools

app = FastAPI(title="teamproject-mcp-server", version="1.0.0")

EXPECTED_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32001,
                "message": "Unauthorized: missing or invalid MCP_AUTH_TOKEN",
            },
        },
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/mcp")
async def mcp(request: Request, authorization: str | None = Header(default=None)) -> JSONResponse:
    # Auth: bearer token must match MCP_AUTH_TOKEN. No token configured -> reject.
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not EXPECTED_TOKEN or token != EXPECTED_TOKEN:
        return _unauthorized()

    raw = await request.body()
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
        )

    # Tools may do blocking network I/O (search) -> run in a worker thread.
    result = await anyio.to_thread.run_sync(jsonrpc.handle, payload, list_tools, call_tool)
    return JSONResponse(status_code=result["http_status"], content=result["body"])
