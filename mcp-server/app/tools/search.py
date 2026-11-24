"""DuckDuckGo internet search tool (migrated from backend stdio MCP server)."""

import json
import logging

logger = logging.getLogger("mcp.tools.search")

SEARCH_SCHEMA = {
    "name": "duckduckgo_search",
    "description": (
        "Search the public internet with DuckDuckGo and return structured results "
        "(title, url, content). Use when the question requires up-to-date or external "
        "knowledge not available in local资料."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Non-empty search query, at most 500 characters.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
                "description": "Maximum number of results to return (1-10).",
            },
        },
        "required": ["query"],
    },
}


class SearchToolError(Exception):
    """Raised when the search tool cannot produce results."""


def _validate_search_args(query: str, max_results: int) -> tuple[str, int]:
    if not isinstance(query, str) or not query.strip():
        raise SearchToolError("query must be a non-empty string")
    query = query.strip()
    if len(query) > 500:
        raise SearchToolError("query must not exceed 500 characters")
    if not isinstance(max_results, int) or max_results < 1 or max_results > 10:
        raise SearchToolError("max_results must be an integer between 1 and 10")
    return query, max_results


def duckduckgo_search(query: str = "", max_results: int = 5) -> str:
    """Search DuckDuckGo and return a JSON string of {title, url, content} results."""
    try:
        query, max_results = _validate_search_args(query, max_results)
    except SearchToolError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    try:
        from ddgs import DDGS
    except ImportError:
        return json.dumps(
            {"error": "search backend unavailable (ddgs not installed)"},
            ensure_ascii=False,
        )

    try:
        with DDGS() as ddgs_client:
            results = ddgs_client.text(query, max_results=max_results)
    except Exception as exc:  # network error, rate limit, timeout, etc.
        logger.warning("duckduckgo_search failed: %s", type(exc).__name__)
        return json.dumps(
            {"error": "search unavailable due to network error or rate limit"},
            ensure_ascii=False,
        )

    if not results:
        return json.dumps({"results": []}, ensure_ascii=False)

    normalized = []
    for item in results:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": str(item.get("title", ""))[:200],
                "url": str(item.get("href", ""))[:500],
                "content": str(item.get("body", ""))[:500],
            }
        )
    return json.dumps({"results": normalized}, ensure_ascii=False)
