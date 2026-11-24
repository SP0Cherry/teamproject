"""HTTP MCP client: invoke a tool on a remote MCP-over-HTTP server (Task 6).

Stateless per call — no persistent session. Returns ``(text, is_error)`` so the
agent loop can classify the outcome and write the right call-record status.
"""

import httpx


async def call_mcp_tool(
    base_url: str,
    token: str | None,
    name: str,
    arguments: dict,
    timeout: float = 20.0,
) -> tuple[str, bool]:
    """Call ``tools/call`` and return ``(text, is_error)``.

    ``is_error`` is True on any transport/HTTP/JSON-RPC failure or when the
    server reports ``isError``.
    """
    url = base_url.rstrip("/") + "/mcp"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "error" in data:
                msg = data["error"].get("message", "unknown")
                return f"error: {msg}", True
            result = data.get("result", {}) if isinstance(data, dict) else {}
            is_error = bool(result.get("isError"))
            parts = [
                block.get("text", "")
                for block in result.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            return "\n".join(parts), is_error
    except Exception as exc:  # noqa: BLE001 - classify any failure as error
        return f"error: {type(exc).__name__}: {exc}", True
