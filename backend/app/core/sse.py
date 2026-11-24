"""Helpers for Server-Sent Events (SSE) streaming responses (Task 7).

The event contract used across QA and notification parse streams:

* ``event: meta``  — ``data`` carries ``tool_calls`` (each with
  ``tool``/``name``/``server``/``status``/``duration_ms``) and ``time_context``.
  Always emitted before the body.
* ``event: tool``  — a single tool call resolved during the loop (incremental,
  before ``meta``). Same shape as a ``meta.tool_calls`` entry.
* ``event: data``  — the body payload (answer + citations, or parsed
  candidates). May be followed by more ``data`` events if chunked.
* ``event: done``  — end of stream.
* ``event: error`` — ``data`` carries ``code``/``message``; stream ends after.
"""

import json


def sse_event(event: str, data) -> str:
    """Format one SSE frame with a JSON ``data`` line."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def sse_error(code: str, message: str) -> str:
    return sse_event("error", {"code": code, "message": message})
