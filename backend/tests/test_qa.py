"""Tests for Q&A with RAG retrieval and authorization (AI-05, SEC-02).

The ask endpoint streams SSE (Task 7); these tests parse the event stream and
assert on the ``data`` event payload, keeping the original coverage.
"""

import json

import pytest
from httpx import AsyncClient


def _parse_sse(text: str):
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        data_parts = []
        for line in block.splitlines():
            if line.startswith("data:"):
                data_parts.append(line[len("data:"):].strip())
        raw = "\n".join(data_parts)
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            events.append(raw)
    return events


def _data_event(text: str):
    for payload in _parse_sse(text):
        if isinstance(payload, dict) and "answer" in payload:
            return payload
    return None


async def _register_and_login(client, username):
    await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "password123"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password123"}
    )
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_qa_with_indexed_attachment(client: AsyncClient, test_upload_dir):
    token = await _register_and_login(client, "qa_user")
    resp = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"Python is a programming language. FastAPI is a web framework.", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = resp.json()["data"]["attachment_id"]

    idx = await client.post(
        f"/api/v1/attachments/{att_id}/index",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert idx.status_code == 200

    resp = await client.post(
        "/api/v1/qa/ask",
        json={"question": "What is Python?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    data = _data_event(resp.text)
    assert data is not None
    assert "answer" in data


@pytest.mark.asyncio
async def test_qa_returns_no_sources_when_empty(client: AsyncClient):
    token = await _register_and_login(client, "qa_empty")
    resp = await client.post(
        "/api/v1/qa/ask",
        json={"question": "anything"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = _data_event(resp.text)
    assert data is not None
    assert data["citations"] == []
