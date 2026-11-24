"""Tool registry: list schemas and dispatch calls by name."""

from .search import duckduckgo_search, SEARCH_SCHEMA
from .unit_convert import unit_convert, CONVERT_SCHEMA

_TOOLS = {
    "duckduckgo_search": {"schema": SEARCH_SCHEMA, "fn": duckduckgo_search},
    "unit_convert": {"schema": CONVERT_SCHEMA, "fn": unit_convert},
}


def list_tools() -> list[dict]:
    """Return all registered tool definitions (MCP tools/list format)."""
    return [tool["schema"] for tool in _TOOLS.values()]


def call_tool(name: str, arguments: dict | None) -> dict:
    """Execute a tool by name and return an MCP tools/call result."""
    tool = _TOOLS.get(name)
    if not tool:
        return {
            "content": [{"type": "text", "text": f"tool not found: {name}"}],
            "isError": True,
        }
    try:
        text = tool["fn"](**(arguments or {}))
        return {"content": [{"type": "text", "text": str(text)}], "isError": False}
    except TypeError as exc:
        return {
            "content": [{"type": "text", "text": f"invalid arguments: {exc}"}],
            "isError": True,
        }
