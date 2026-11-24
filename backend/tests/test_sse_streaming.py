"""SSE streaming contract tests for QA ask and notification parse (Task 7).

Verifies: event-stream content type, ``meta`` precedes ``data``, tool call
statuses are visible (success/rejected), rejected calls produce no outbound
request, the no-tools main path is not blocked, and tool calls do not alter
notification time results.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.crypto import encrypt_secret
from app.models.skill import Skill, SkillCapability
from app.models.tool_server import ServerStatus, ToolServer
from app.models.user import User


def _parse_sse(text: str):
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data_parts = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_parts.append(line[len("data:"):].strip())
        raw = "\n".join(data_parts)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = raw
        events.append((event, data))
    return events


def _event_names(events):
    return [e for e, _ in events]


def _first(events, name):
    for e, d in events:
        if e == name:
            return d
    return None


async def _register_login(client, db_session, username):
    await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "password123"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password123"}
    )
    token = resp.json()["data"]["access_token"]
    row = (
        await db_session.execute(select(User).where(User.username == username))
    ).scalar_one()
    return token, row.id


async def _seed_connected_tool(db_session, owner_id, capability, tool_name="search"):
    server = ToolServer(
        owner_id=owner_id,
        name="srv",
        base_url="http://x:8090",
        token_cipher=encrypt_secret("tok"),
        has_token=True,
        status=ServerStatus.CONNECTED,
        discovered_tools=json.dumps(
            [
                {
                    "name": tool_name,
                    "description": "web search",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                }
            ]
        ),
    )
    db_session.add(server)
    skill = Skill(
        owner_id=owner_id,
        name="skill",
        capability=SkillCapability(capability),
        tool_refs=json.dumps([f"{tool_name}@srv"]),
        version=1,
    )
    db_session.add(skill)
    await db_session.commit()


def _msg(content=None, tool_calls=None, time_context=None):
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": tool_calls,
        "time_context": time_context,
    }


def _tool_call(name, arguments, call_id="c1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


@pytest.mark.asyncio
async def test_qa_sse_envelope_and_meta_before_data(client, db_session):
    token, _ = await _register_login(client, db_session, "qa_stream")
    # Index one attachment so retrieval returns chunks and the loop runs.
    up = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"Python is a programming language.", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = up.json()["data"]["attachment_id"]
    await client.post(
        f"/api/v1/attachments/{att_id}/index",
        headers={"Authorization": f"Bearer {token}"},
    )

    model = AsyncMock(return_value=_msg(content="本地资料回答"))
    with patch("app.services.agent.loop.chat_completion_with_tools", new=model):
        resp = await client.post(
            "/api/v1/qa/ask",
            json={"question": "What is Python?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    names = _event_names(events)
    assert "meta" in names and "data" in names and "done" in names
    assert names.index("meta") < names.index("data")  # meta precedes body
    data = _first(events, "data")
    assert "answer" in data
    assert "error" not in names


@pytest.mark.asyncio
async def test_notification_parse_tool_success_streams_meta(client, db_session):
    token, user_id = await _register_login(client, db_session, "np_stream")
    await _seed_connected_tool(db_session, user_id, "notification_extraction")

    parsed_json = json.dumps(
        {"title": "t", "content": "c", "items": [{"text": "明天开会"}]}
    )
    model = AsyncMock(
        side_effect=[
            _msg(tool_calls=[_tool_call("search", {"query": "x"})]),
            _msg(content=parsed_json),
        ]
    )
    http = AsyncMock(return_value=("web result", False))
    with patch("app.services.agent.loop.chat_completion_with_tools", new=model), patch(
        "app.services.agent.loop.call_mcp_tool", new=http
    ):
        resp = await client.post(
            "/api/v1/notifications/parse",
            json={"text": "明天开会"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    names = _event_names(events)
    assert "tool" in names
    tool_data = _first(events, "tool")
    assert tool_data["status"] == "success"
    assert tool_data["tool"] == "search@srv"
    meta = _first(events, "meta")
    assert meta["tool_calls"][0]["status"] == "success"
    assert names.index("meta") < names.index("data")
    data = _first(events, "data")
    assert data["items"] and data["time_context"]
    assert http.await_count == 1  # outbound call happened for the valid tool


@pytest.mark.asyncio
async def test_notification_parse_rejected_no_outbound(client, db_session):
    token, user_id = await _register_login(client, db_session, "np_reject")
    await _seed_connected_tool(db_session, user_id, "notification_extraction")

    parsed_json = json.dumps({"title": "t", "content": "c", "items": []})
    model = AsyncMock(
        side_effect=[
            _msg(tool_calls=[_tool_call("evil_tool", {})]),
            _msg(content=parsed_json),
        ]
    )
    http = AsyncMock(return_value=("x", False))
    with patch("app.services.agent.loop.chat_completion_with_tools", new=model), patch(
        "app.services.agent.loop.call_mcp_tool", new=http
    ):
        resp = await client.post(
            "/api/v1/notifications/parse",
            json={"text": "明天开会"},
            headers={"Authorization": f"Bearer {token}"},
        )

    events = _parse_sse(resp.text)
    assert http.await_count == 0  # rejected -> no outbound request
    meta = _first(events, "meta")
    assert meta["tool_calls"][0]["status"] == "rejected"
    tool_data = _first(events, "tool")
    assert tool_data["status"] == "rejected"


@pytest.mark.asyncio
async def test_notification_parse_unconnected_server_shows_rejected(
    client, db_session
):
    token, user_id = await _register_login(client, db_session, "np_unconn")
    server = ToolServer(
        owner_id=user_id,
        name="srv",
        base_url="http://x:8090",
        token_cipher=encrypt_secret("tok"),
        has_token=True,
        status=ServerStatus.UNCONNECTED,
        discovered_tools=json.dumps([{"name": "search"}]),
    )
    db_session.add(server)
    skill = Skill(
        owner_id=user_id,
        name="sk",
        capability=SkillCapability.NOTIFICATION_EXTRACTION,
        tool_refs=json.dumps(["search@srv"]),
        version=1,
    )
    db_session.add(skill)
    await db_session.commit()

    parsed_json = json.dumps({"title": "t", "content": "c", "items": []})
    model = AsyncMock(return_value=_msg(content=parsed_json))
    http = AsyncMock(return_value=("x", False))
    with patch(
        "app.services.agent.loop.chat_completion_with_tools", new=model
    ), patch("app.services.agent.loop.call_mcp_tool", new=http):
        resp = await client.post(
            "/api/v1/notifications/parse",
            json={"text": "明天开会"},
            headers={"Authorization": f"Bearer {token}"},
        )

    events = _parse_sse(resp.text)
    assert http.await_count == 0  # disconnected tool is never called
    meta = _first(events, "meta")
    rejected = [c for c in meta["tool_calls"] if c["status"] == "rejected"]
    assert any(c["tool"] == "search@srv" for c in rejected)
    # Main path is not blocked: body data still delivered.
    assert _first(events, "data") is not None
    assert "error" not in _event_names(events)


@pytest.mark.asyncio
async def test_notification_parse_tool_does_not_change_time(client, db_session):
    token, user_id = await _register_login(client, db_session, "np_time")
    await _seed_connected_tool(db_session, user_id, "notification_extraction")

    parsed_json = json.dumps(
        {
            "title": "t",
            "content": "c",
            "items": [{"text": "明天下午3点交报告", "date_expression": "明天"}],
        }
    )

    async def _parse(with_tool: bool):
        if with_tool:
            model = AsyncMock(
                side_effect=[
                    _msg(tool_calls=[_tool_call("search", {"query": "x"})]),
                    _msg(content=parsed_json),
                ]
            )
        else:
            model = AsyncMock(return_value=_msg(content=parsed_json))
        http = AsyncMock(return_value=("web result", False))
        with patch(
            "app.services.agent.loop.chat_completion_with_tools", new=model
        ), patch("app.services.agent.loop.call_mcp_tool", new=http):
            resp = await client.post(
                "/api/v1/notifications/parse",
                json={"text": "明天下午3点交报告"},
                headers={"Authorization": f"Bearer {token}"},
            )
        events = _parse_sse(resp.text)
        return events, http.await_count

    with_tool_events, with_http = await _parse(with_tool=True)
    without_tool_events, without_http = await _parse(with_tool=False)

    # The tool call actually happened in the with-tool run only.
    assert with_http == 1 and without_http == 0
    assert "tool" in _event_names(with_tool_events)
    assert "tool" not in _event_names(without_tool_events)

    with_data = _first(with_tool_events, "data")
    without_data = _first(without_tool_events, "data")
    # Time fields come from the trusted snapshot + deterministic rules and are
    # identical regardless of whether a tool was called (spec: tool status
    # must not overwrite or alter time results).
    assert with_data["time_context"] == without_data["time_context"]
    with_item = with_data["items"][0]
    without_item = without_data["items"][0]
    assert with_item["date"] is not None  # deterministic date computation ran
    assert with_item["date"] == without_item["date"]
    assert with_item["time"] == without_item["time"]
    assert with_item["date_basis"] == without_item["date_basis"]

