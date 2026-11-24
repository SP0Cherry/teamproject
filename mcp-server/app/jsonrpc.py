"""Minimal JSON-RPC 2.0 dispatcher for the MCP methods we expose."""


def _error(req_id, code: int, message: str, http_status: int = 200) -> dict:
    return {
        "http_status": http_status,
        "body": {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}},
    }


def handle(payload, list_tools_fn, call_tool_fn) -> dict:
    """Dispatch a parsed JSON-RPC 2.0 payload. Always returns {http_status, body}."""
    if not isinstance(payload, dict):
        return _error(None, -32600, "Invalid Request", http_status=400)

    req_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params")

    if not isinstance(method, str):
        return _error(req_id, -32600, "Invalid Request: method must be a string")

    if method == "initialize":
        return {
            "http_status": 200,
            "body": {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "teamproject-mcp-server", "version": "1.0.0"},
                },
            },
        }

    if method == "tools/list":
        return {
            "http_status": 200,
            "body": {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list_tools_fn()}},
        }

    if method == "tools/call":
        if not isinstance(params, dict):
            return _error(req_id, -32602, "Invalid params: params must be an object")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            return _error(req_id, -32602, "Invalid params: name is required")
        if not isinstance(arguments, dict):
            return _error(req_id, -32602, "Invalid params: arguments must be an object")
        result = call_tool_fn(name, arguments)
        return {"http_status": 200, "body": {"jsonrpc": "2.0", "id": req_id, "result": result}}

    return _error(req_id, -32601, f"Method not found: {method}", http_status=404)
