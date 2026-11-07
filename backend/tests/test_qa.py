"""Tests for Q&A with RAG retrieval and authorization (AI-05, SEC-02)."""

import pytest
from httpx import AsyncClient


async def _register_and_login(client, username):
    await client.post(
        "/api/v1/auth/register", json={"username": username, "password": "password123"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password123"}
    )
    return resp.json()["data"]["access_token"]


async def _create_group(client, token, name="g1"):
    resp = await client.post(
        "/api/v1/groups",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["data"]["id"], resp.json()["data"]["invite_token"]


@pytest.mark.asyncio
async def test_qa_with_indexed_attachment(client: AsyncClient, test_upload_dir):
    token = await _register_and_login(client, "qa_user")
    # Upload and index a text attachment
    resp = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"Python is a programming language. FastAPI is a web framework.", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = resp.json()["data"]["attachment_id"]

    # Index the attachment (no extracted text yet, returns 0 chunks)
    idx = await client.post(
        f"/api/v1/attachments/{att_id}/index",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert idx.status_code == 200

    # Ask a question
    resp = await client.post(
        "/api/v1/qa/ask",
        json={"question": "What is Python?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
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
    data = resp.json()["data"]
    assert data["citations"] == []
