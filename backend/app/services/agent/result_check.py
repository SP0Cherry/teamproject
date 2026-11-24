"""Sanitize tool results before they are fed back to the model (AI-08, SEC-11).

Two safety measures:
1. Drop lines that look like instructions attempting to override system rules
   (instruction-injection defence). The result is data, never instructions.
2. Truncate to ``TOOL_RESULT_MAX_CHARS`` so a single huge result cannot
   dominate the context window or exhaust limits.
"""

import re

from app.core.config import settings

_INSTRUCTION_RE = re.compile(
    r"(?i)^\s*(ignore|disregard|forget|you are|act as|system:|assistant:|"
    r"reveal|do not follow|new instructions?|override)\b"
)


def sanitize_tool_result(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if _INSTRUCTION_RE.match(line):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    limit = settings.tool_result_max_chars
    if len(cleaned) > limit:
        cleaned = cleaned[:limit] + "\n...[truncated]"
    return cleaned
