"""Tests for todo parsing: multi-item, field null, LLM fallback, rule fallback (AI-06, AI-05)."""

import json
from unittest.mock import patch, AsyncMock

import pytest

from app.services.model import ModelError, validate_output
from app.services.todo_parser import (
    TODO_SCHEMA,
    _demo_parse,
    _has_multiple_segments,
    parse_todos,
)


class TestDemoParseMultiItem:
    """Rule-based parser handles multi-item Chinese text."""

    def test_chinese_multi_item(self):
        text = "明天上午十点开会，下午三点交报告，晚上八点和朋友吃饭"
        todos = _demo_parse(text)
        titles = [t["title"] for t in todos]
        assert len(todos) >= 3
        assert any("开会" in t for t in titles)
        assert any("报告" in t for t in titles)
        assert any("吃饭" in t for t in titles)

    def test_today_tomorrow(self):
        text = "今天开会，明天交报告"
        todos = _demo_parse(text)
        assert len(todos) == 2

    def test_single_item(self):
        todos = _demo_parse("买牛奶")
        assert len(todos) == 1
        assert todos[0]["title"] == "买牛奶"


class TestDemoParseFields:
    """Field extraction: missing fields are None, not dropped."""

    def test_time_chinese_numeral(self):
        todos = _demo_parse("下午三点开会")
        assert todos[0]["time"] == "15:00"

    def test_location(self):
        todos = _demo_parse("在会议室A开会")
        assert todos[0]["location"] == "会议室A"

    def test_missing_fields_are_none(self):
        todos = _demo_parse("买牛奶")
        assert todos[0]["date"] is None
        assert todos[0]["time"] is None
        assert todos[0]["location"] is None


class TestHasMultipleSegments:
    def test_multi_segment(self):
        assert _has_multiple_segments("明天开会，后天交报告") is True

    def test_single_segment(self):
        assert _has_multiple_segments("买牛奶") is False


class TestValidateOutputItems:
    """validate_output drops invalid items but keeps valid ones (AI-06)."""

    def test_valid_items_pass(self):
        data = {"todos": [{"title": "a", "date": None}, {"title": "b"}]}
        result = validate_output(data, TODO_SCHEMA)
        assert len(result["todos"]) == 2

    def test_item_missing_title_dropped(self):
        data = {"todos": [{"title": "a"}, {"date": "2024-01-01"}]}
        result = validate_output(data, TODO_SCHEMA)
        assert len(result["todos"]) == 1
        assert result["todos"][0]["title"] == "a"

    def test_item_wrong_type_dropped(self):
        data = {"todos": [{"title": "a"}, {"title": 123}]}
        result = validate_output(data, TODO_SCHEMA)
        assert len(result["todos"]) == 1

    def test_null_optional_fields_kept(self):
        data = {"todos": [{"title": "a", "date": None, "time": None, "location": None, "notes": None}]}
        result = validate_output(data, TODO_SCHEMA)
        assert len(result["todos"]) == 1
        assert result["todos"][0]["date"] is None


@pytest.mark.asyncio
class TestParseTodosFallback:
    """LLM failure falls back to rule parsing (AI-05)."""

    async def test_llm_model_error_falls_back(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = ModelError("timeout")
            result = await parse_todos(
                "明天开会，后天交报告",
                llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
            )
            assert result["parser"] == "rule"
            assert len(result["candidates"]) >= 2

    async def test_llm_invalid_json_falls_back(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "not json at all"
            result = await parse_todos(
                "明天开会",
                llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
            )
            assert result["parser"] == "rule"
            assert len(result["candidates"]) >= 1

    async def test_llm_empty_todos_falls_back_for_multi_segment(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = json.dumps({"todos": []})
            result = await parse_todos(
                "明天开会，后天交报告",
                llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
            )
            assert result["parser"] == "rule"
            assert len(result["candidates"]) >= 2

    async def test_llm_success_uses_llm(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = json.dumps(
                {"todos": [{"title": "开会", "date": None, "time": None, "location": None, "notes": None}]}
            )
            result = await parse_todos(
                "明天开会",
                llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
            )
            assert result["parser"] == "llm"
            assert len(result["candidates"]) == 1


@pytest.mark.asyncio
class TestParseTodosDemoMode:
    """Demo mode (no LLM config) uses rule parser directly."""

    async def test_demo_mode_multi_item(self):
        result = await parse_todos("今天开会，明天交报告，后天复习")
        assert result["parser"] == "rule"
        assert len(result["candidates"]) >= 3
