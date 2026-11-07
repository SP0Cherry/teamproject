"""Notification extraction: parse text into structured candidates (AI-02, AI-04, AI-06).

Uses the model adapter to extract title, content, deadline, and action items.
Output is validated against a schema. Deadline is parsed and normalized to UTC.
"""

import json
import re
from datetime import datetime, timedelta, timezone

from app.core.response import ApiError
from app.services.model import ModelError, chat_completion, validate_output

NOTIFICATION_SCHEMA = {
    "type": "object",
    "required": ["title", "content", "items"],
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "deadline": {"type": "string"},
        "items": {"type": "array"},
    },
}

EXTRACTION_PROMPT = """你是一个通知解析助手。从用户提供的通知原文中提取结构化信息。
输出 JSON，字段说明：
- title: 通知标题（简短）
- content: 通知正文摘要
- deadline: 截止时间，ISO 8601 格式（UTC）；若无截止时间则为 null
- items: 从通知中识别出的待办事项列表，每项为 {"text": "事项描述", "deadline": "ISO时间或null"}
只输出 JSON，不要额外说明。"""


class ExtractionError(ApiError):
    def __init__(self, message: str):
        super().__init__(code="BUSINESS_RULE", message=message)


async def extract_notification(text: str) -> dict:
    """Extract structured notification candidates from text."""
    if not text or not text.strip():
        raise ExtractionError("empty notification text")

    try:
        raw = await chat_completion(
            system_prompt=EXTRACTION_PROMPT,
            user_content=text,
            response_schema=NOTIFICATION_SCHEMA,
        )
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ExtractionError("model output is not valid JSON")
    except ModelError as e:
        raise ExtractionError(f"extraction failed: {e}")

    validated = validate_output(data, NOTIFICATION_SCHEMA)

    # Normalize deadline
    deadline = validated.get("deadline")
    if deadline:
        validated["deadline"] = _normalize_deadline(deadline)

    # Normalize items
    items = validated.get("items", [])
    normalized_items = []
    for item in items:
        if isinstance(item, dict) and "text" in item:
            item_deadline = item.get("deadline")
            if item_deadline:
                item_deadline = _normalize_deadline(item_deadline)
            normalized_items.append(
                {"text": str(item["text"]).strip(), "deadline": item_deadline}
            )
    validated["items"] = normalized_items

    return validated


def _normalize_deadline(value: str) -> str | None:
    """Parse and normalize a deadline to ISO 8601 UTC. Returns None if unparseable."""
    if not value:
        return None
    value = value.strip()

    # Try ISO 8601
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue

    # Relative dates: today, tomorrow, +Nd
    now = datetime.now(timezone.utc)
    low = value.lower()
    if low == "today":
        return now.isoformat()
    if low == "tomorrow":
        return (now + timedelta(days=1)).isoformat()
    m = re.match(r"\+(\d+)d", low)
    if m:
        return (now + timedelta(days=int(m.group(1)))).isoformat()

    return None
