"""HTTP MCP discovery: initialize handshake + tools/list (Task 3, Task 6 reuse).

Talks to an MCP-over-HTTP server's single ``POST /mcp`` JSON-RPC endpoint. Two
steps must both succeed; any failure raises ``McpDiscoveryError`` with a
readable message so the service layer can record ``last_error`` without
leaking internals.
"""

import httpx


class McpDiscoveryError(Exception):
    """Raised when the MCP server cannot be reached or returns an error."""


async def discover_tools(
    base_url: str, token: str | None, timeout: float = 10.0
) -> list[dict]:
    url = base_url.rstrip("/") + "/mcp"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            init = await client.post(
                url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            init.raise_for_status()
            init_data = init.json()
            if isinstance(init_data, dict) and "error" in init_data:
                raise McpDiscoveryError(
                    f"initialize 失败: {init_data['error'].get('message', 'unknown')}"
                )

            listed = await client.post(
                url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            listed.raise_for_status()
            list_data = listed.json()
            if isinstance(list_data, dict) and "error" in list_data:
                raise McpDiscoveryError(
                    f"tools/list 失败: {list_data['error'].get('message', 'unknown')}"
                )
            tools = list_data.get("result", {}).get("tools", [])
            if not isinstance(tools, list):
                raise McpDiscoveryError("tools/list 返回的工具清单格式错误")
            return tools
    except httpx.TimeoutException:
        raise McpDiscoveryError("连接工具服务器超时") from None
    except httpx.ConnectError:
        raise McpDiscoveryError("无法连接工具服务器") from None
    except httpx.HTTPStatusError as exc:
        raise McpDiscoveryError(f"工具服务器返回 HTTP {exc.response.status_code}") from None
    except (httpx.HTTPError, ValueError) as exc:
        raise McpDiscoveryError(f"工具服务器响应异常: {exc}") from None
