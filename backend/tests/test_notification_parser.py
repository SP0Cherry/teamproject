"""Tests for model adapter, notification parser, and source auth (AI-04, SEC-13)."""

import json
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.model import ModelError, validate_output
from app.services.notification_parser import _normalize_deadline, extract_notification


class TestValidateOutput:
    def test_valid_output_passes(self):
        schema = {
            "required": ["title", "items"],
            "properties": {"title": {"type": "string"}, "items": {"type": "array"}},
        }
        data = {"title": "hello", "items": [{"text": "a"}], "extra": "strip me"}
        result = validate_output(data, schema)
        assert result == {"title": "hello", "items": [{"text": "a"}]}

    def test_missing_required_raises(self):
        schema = {"required": ["title"], "properties": {"title": {"type": "string"}}}
        with pytest.raises(ModelError):
            validate_output({}, schema)

    def test_wrong_type_raises(self):
        schema = {"required": ["title"], "properties": {"title": {"type": "string"}}}
        with pytest.raises(ModelError):
            validate_output({"title": 123}, schema)

    def test_non_object_raises(self):
        schema = {"required": ["title"], "properties": {}}
        with pytest.raises(ModelError):
            validate_output("not an object", schema)


class TestNormalizeDeadline:
    def test_iso_with_tz(self):
        result = _normalize_deadline("2026-06-15T10:00:00+08:00")
        assert result is not None
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None
        # UTC: 10:00 +08:00 = 02:00 UTC
        assert dt.hour == 2

    def test_iso_no_tz_treated_as_utc(self):
        result = _normalize_deadline("2026-06-15T10:00:00")
        assert result is not None
        dt = datetime.fromisoformat(result)
        assert dt.hour == 10

    def test_date_only(self):
        result = _normalize_deadline("2026-06-15")
        assert result is not None

    def test_today(self):
        result = _normalize_deadline("today")
        assert result is not None

    def test_tomorrow(self):
        result = _normalize_deadline("tomorrow")
        assert result is not None

    def test_plus_days(self):
        result = _normalize_deadline("+3d")
        assert result is not None

    def test_invalid_returns_none(self):
        result = _normalize_deadline("not a date")
        assert result is None

    def test_empty_returns_none(self):
        assert _normalize_deadline("") is None
        assert _normalize_deadline(None) is None


@pytest.mark.asyncio
async def test_extract_notification_demo_mode():
    """Demo mode returns deterministic structured output (AI-08)."""
    assert settings.is_demo_mode
    result = await extract_notification("明天下午3点开会")
    assert "title" in result
    assert "content" in result
    assert "items" in result
    assert isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_extract_empty_text_fails():
    from app.services.notification_parser import ExtractionError

    with pytest.raises(ExtractionError):
        await extract_notification("")


@pytest.mark.asyncio
async def test_source_auth_invalid_rejected(client: AsyncClient):
    """Invalid source credentials are rejected (SEC-13)."""
    resp = await client.post(
        "/api/v1/notifications/ingest",
        json={"text": "hello", "owner_id": "u1"},
        headers={"source": "demo-source", "x-source-token": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_source_ingest_demo_mode(client: AsyncClient):
    """Valid source can ingest and gets parsed candidates in demo mode."""
    resp = await client.post(
        "/api/v1/notifications/ingest",
        json={"text": "周五提交项目报告", "owner_id": "user-123"},
        headers={"source": "demo-source", "x-source-token": "demo-secret-change-me"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "pending"
    assert "candidates" in body["data"]
