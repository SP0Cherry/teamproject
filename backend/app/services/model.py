"""AI model adapter with demo mode fallback (AI-01, AI-03, AI-04, AI-08).

In demo mode (no LLM config), returns deterministic canned output. In real mode,
calls the configured LLM endpoint. All outputs are validated against a schema.
"""

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("model")


class ModelError(Exception):
    pass


async def chat_completion(
    system_prompt: str,
    user_content: str,
    response_schema: dict | None = None,
    timeout: float = 30.0,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    """Call the LLM and return raw text. Raises ModelError on failure.

    Per-request credentials (api_key/base_url/model) override the global
    settings. If neither global nor per-request config is present, falls
    back to demo mode.
    """
    use_api_key = api_key or settings.llm_api_key
    use_base_url = base_url or settings.llm_base_url
    use_model = model or settings.llm_model

    if not (use_base_url and use_api_key and use_model):
        return _demo_response(system_prompt, user_content)

    payload: dict[str, Any] = {
        "model": use_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }
    if response_schema:
        payload["response_format"] = {"type": "json_object", "schema": response_schema}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{use_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {use_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.info(
                "llm_response",
                model=use_model,
                user_input=user_content[:500],
                raw_response=content,
            )
            return content
    except httpx.TimeoutException:
        raise ModelError("LLM timeout")
    except httpx.HTTPError as e:
        raise ModelError(f"LLM request failed: {e}")
    except (KeyError, IndexError) as e:
        raise ModelError(f"LLM response malformed: {e}")


def _demo_response(system_prompt: str, user_content: str) -> str:
    """Deterministic demo output for testing without an external LLM (AI-08)."""
    # For notification extraction demo
    if "notification" in system_prompt.lower() or "通知" in system_prompt:
        return json.dumps(
            {
                "title": "通知",
                "content": user_content[:200],
                "deadline": None,
                "items": [],
            },
            ensure_ascii=False,
        )
    # For todo parsing demo: create a single todo from the input
    if "todo" in system_prompt.lower() or "待办" in system_prompt:
        # Try to extract a simple title from the input
        title = user_content.strip()[:50] or "新待办"
        return json.dumps(
            {
                "todos": [
                    {
                        "title": title,
                        "date": None,
                        "time": None,
                        "location": None,
                        "notes": user_content[:200],
                    }
                ]
            },
            ensure_ascii=False,
        )
    return json.dumps({"answer": "演示模式：未连接模型"}, ensure_ascii=False)


def validate_output(data: dict, schema: dict) -> dict:
    """Validate model output against a simple JSON schema (AI-04, AI-06).

    Supports type, required, properties, and items (for arrays). Returns
    cleaned data or raises ModelError. Invalid array items are dropped
    rather than failing the whole validation, as long as the array itself
    is present.
    """
    if not isinstance(data, dict):
        raise ModelError("output is not an object")

    required = schema.get("required", [])
    for field in required:
        if field not in data:
            raise ModelError(f"missing required field: {field}")

    properties = schema.get("properties", {})
    cleaned: dict[str, Any] = {}
    for field, value in data.items():
        if field not in properties:
            continue  # strip unknown fields
        # Allow null for optional (non-required) fields
        if value is None and field not in required:
            cleaned[field] = value
            continue
        expected_type = properties[field].get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise ModelError(f"field {field} must be string")
        if expected_type == "array" and not isinstance(value, list):
            raise ModelError(f"field {field} must be array")
        if expected_type == "object" and not isinstance(value, dict):
            raise ModelError(f"field {field} must be object")
        # Validate array items if schema specifies items
        if expected_type == "array" and isinstance(value, list) and "items" in properties[field]:
            item_schema = properties[field]["items"]
            cleaned_items = []
            for item in value:
                validated_item = _validate_item(item, item_schema)
                if validated_item is not None:
                    cleaned_items.append(validated_item)
            cleaned[field] = cleaned_items
        else:
            cleaned[field] = value

    return cleaned


def _validate_item(item: Any, item_schema: dict) -> dict | None:
    """Validate a single array item against its schema.

    Returns the cleaned item dict, or None if the item is invalid and
    should be dropped.
    """
    if not isinstance(item, dict):
        return None
    required = item_schema.get("required", [])
    for field in required:
        if field not in item or item[field] is None:
            return None  # drop items missing required fields
    properties = item_schema.get("properties", {})
    cleaned: dict[str, Any] = {}
    for field, value in item.items():
        if field not in properties:
            continue
        if value is None:
            cleaned[field] = value
            continue
        expected_type = properties[field].get("type")
        if expected_type == "string" and not isinstance(value, str):
            return None  # drop items with wrong field types
        cleaned[field] = value
    return cleaned
