"""Tests for attachment upload, quota validation, and extraction (SEC-08, BE-13)."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import UploadFile
from httpx import AsyncClient

from app.core.config import settings
from app.models.attachment import Attachment, AttachmentStatus


async def _register_and_login(client, username):
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_upload_text_file_returns_202(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    token = await _register_and_login(client, "uploader")

    files = {"file": ("hello.txt", io.BytesIO(b"hello world"), "text/plain")}
    resp = await client.post(
        "/api/v1/attachments",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["code"] == "OK"
    assert "task_id" in body["data"]
    assert body["data"]["filename"] == "hello.txt"


@pytest.mark.asyncio
async def test_unsupported_file_type_rejected(client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    token = await _register_and_login(client, "typecheck")

    files = {"file": ("data.bin", io.BytesIO(b"\x00\x01\x02"), "application/octet-stream")}
    resp = await client.post(
        "/api/v1/attachments",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


@pytest.mark.asyncio
async def test_oversized_file_rejected(client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    token = await _register_and_login(client, "sizecheck")

    big = b"x" * (2 * 1024 * 1024)
    files = {"file": ("big.txt", io.BytesIO(big), "text/plain")}
    resp = await client.post(
        "/api/v1/attachments",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


@pytest.mark.asyncio
async def test_empty_file_rejected(client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    token = await _register_and_login(client, "emptycheck")

    files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    resp = await client.post(
        "/api/v1/attachments",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


@pytest.mark.asyncio
async def test_extract_text_success(db_session, tmp_path, monkeypatch):
    from app.services.extractor import extract_text

    f = tmp_path / "test.txt"
    f.write_text("hello extraction", encoding="utf-8")
    text, err = extract_text(str(f), "text/plain")
    assert err == ""
    assert text == "hello extraction"


@pytest.mark.asyncio
async def test_extract_empty_text_fails(db_session, tmp_path):
    from app.services.extractor import extract_text

    f = tmp_path / "empty.txt"
    f.write_text("   \n  ", encoding="utf-8")
    text, err = extract_text(str(f), "text/plain")
    assert err == "empty text"
    assert text == ""


@pytest.mark.asyncio
async def test_extract_image_with_ocr(db_session, tmp_path):
    from app.services.extractor import extract_text

    # Create a minimal valid PNG
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="white")
    f = tmp_path / "test.png"
    img.save(f)

    def fake_ocr(path):
        return "ocr extracted text"

    text, err = extract_text(str(f), "image/png", ocr_fn=fake_ocr)
    assert err == ""
    assert text == "ocr extracted text"


@pytest.mark.asyncio
async def test_extract_image_ocr_no_text_fails(db_session, tmp_path):
    from app.services.extractor import extract_text
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="white")
    f = tmp_path / "blank.png"
    img.save(f)

    def fake_ocr(path):
        return ""

    text, err = extract_text(str(f), "image/png", ocr_fn=fake_ocr)
    assert err == "ocr returned no text"
    assert text == ""


@pytest.mark.asyncio
async def test_attachment_owner_isolation(client: AsyncClient, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    token_a = await _register_and_login(client, "owner_a_att")
    token_b = await _register_and_login(client, "owner_b_att")

    files = {"file": ("note.txt", io.BytesIO(b"secret note"), "text/plain")}
    resp = await client.post(
        "/api/v1/attachments",
        files=files,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    att_id = resp.json()["data"]["attachment_id"]

    # User B cannot see user A's attachment
    resp = await client.get(
        f"/api/v1/attachments/{att_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
