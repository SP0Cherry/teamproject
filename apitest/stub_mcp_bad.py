"""Faulty MCP-over-HTTP server for apitest (TEST-05): deterministically errors.

initialize and tools/list succeed (so the host can connect and discover the
`boom` tool), but tools/call always returns a JSON-RPC error -> the host
classifies the call as `error` and persists an ERROR record.
"""

import json
import os

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="apitest-stub-mcp-bad")

EXPECTED_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")

BOOM_TOOL = {
    "name": "boom",
    "description": "Always fails; used to exercise the error record path.",
    "inputSchema": {"type": "object"},
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/mcp")
async def mcp(request: Request, authorization: str | None = Header(default=None)):
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not EXPECTED_TOKEN or token != EXPECTED_TOKEN:
        return JSONResponse(
            status_code=401,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32001, "message": "Unauthorized"},
            },
        )

    try:
        payload = json.loads(await request.body())
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
        )

    req_id = payload.get("id")
    method = payload.get("method")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bad-mcp", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [BOOM_TOOL]}}
    if method == "tools/call":
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": "boom: simulated tool failure"},
            },
        )
    return JSONResponse(
        status_code=404,
        content={"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}},
    )
