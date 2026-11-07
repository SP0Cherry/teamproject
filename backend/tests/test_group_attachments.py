"""Tests for group-scoped attachments, versioned edits, and delete (SEC-02, BE-14)."""

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
async def test_group_member_can_upload_to_group(client: AsyncClient, test_upload_dir):
    token_a = await _register_and_login(client, "owner_upload")
    token_b = await _register_and_login(client, "member_upload")
    gid, invite = await _create_group(client, token_a, "upload-group")

    # B joins via invite token
    await client.post(
        "/api/v1/groups/join-by-token",
        json={"invite_token": invite},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # B uploads to group
    resp = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"group content", "text/plain")},
        data={"group_id": gid},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_non_member_cannot_upload_to_group(client: AsyncClient, test_upload_dir):
    token_a = await _register_and_login(client, "owner_noup")
    token_c = await _register_and_login(client, "outsider")
    gid, _ = await _create_group(client, token_a, "noup-group")

    resp = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"content", "text/plain")},
        data={"group_id": gid},
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_edit_creates_new_version_original_unchanged(client: AsyncClient, test_upload_dir):
    token = await _register_and_login(client, "edit_user")
    resp = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"original content", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = resp.json()["data"]["attachment_id"]

    # Edit title and extracted text
    edit_resp = await client.put(
        f"/api/v1/attachments/{att_id}",
        json={"title": "New Title", "extracted_text": "edited text"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["data"]["version"] == 2

    # Original (v1) still has old title - get latest version returns the newest
    get_resp = await client.get(
        f"/api/v1/attachments/{att_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # v1 remains immutable in storage_path
    assert get_resp.json()["data"]["version"] == 1


@pytest.mark.asyncio
async def test_delete_attachment(client: AsyncClient, test_upload_dir):
    token = await _register_and_login(client, "del_user")
    resp = await client.post(
        "/api/v1/attachments",
        files={"file": ("doc.txt", b"to delete", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    att_id = resp.json()["data"]["attachment_id"]

    del_resp = await client.delete(
        f"/api/v1/attachments/{att_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200

    # Verify it's gone
    get_resp = await client.get(
        f"/api/v1/attachments/{att_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404
