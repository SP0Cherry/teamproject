"""Offline stub LLM for apitest (TEST-05): no real model calls.

Returns canned OpenAI-shaped chat completions. The first call that includes
`tools` emits a single tool_call chosen by a keyword in the user message; any
call whose history already contains a `tool` role (or has no tools) returns a
final content message with no tool_calls, ending the agent loop after one call.

Keyword -> behavior (matched against the last user message):
  * TRIGGER_SUCCESS  -> unit_convert with valid args   (record: success)
  * TRIGGER_REJECTED -> unit_convert missing required  (record: rejected)
  * TRIGGER_ERROR    -> boom on the faulty server       (record: error)
  * otherwise         -> unit_convert valid args        (record: success)
"""

import json

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="apitest-stub-llm")

_PARSE_JSON = json.dumps(
    {"title": "测试通知", "content": "解析摘要", "deadline": None, "items": []},
    ensure_ascii=False,
)
_QA_TEXT = "根据本地资料与工具结果回答：10 米等于 32.8 英尺。"


class ChatRequest(BaseModel):
    model: str
    messages: list
    tools: list | None = None
    temperature: float | None = None
    response_format: dict | None = None


def _is_parse(messages: list) -> bool:
    return any(
        "通知语义解析" in (m.get("content") or "")
        for m in messages
        if m.get("role") == "system"
    )


def _last_user_text(messages: list) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _tool_call(name: str, arguments: dict) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        ],
    }


def _choice(message: dict) -> dict:
    return {
        "choices": [{"message": message}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat(req: ChatRequest):
    messages = req.messages
    tools = req.tools
    has_tool_result = any(m.get("role") == "tool" for m in messages)
    is_parse = _is_parse(messages)

    if has_tool_result or not tools:
        content = _PARSE_JSON if is_parse else _QA_TEXT
        return _choice({"role": "assistant", "content": content, "tool_calls": None})

    text = _last_user_text(messages)
    if "TRIGGER_REJECTED" in text:
        return _choice(_tool_call("unit_convert", {"value": 10}))
    if "TRIGGER_ERROR" in text:
        return _choice(_tool_call("boom", {"x": 1}))
    return _choice(
        _tool_call("unit_convert", {"value": 10, "from_unit": "m", "to_unit": "ft"})
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
