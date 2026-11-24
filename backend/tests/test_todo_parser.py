"""Tests for todo parsing: field validation, LLM success, and error handling (AI-06, AI-05).

Parsing always calls the LLM agent. LLM unavailability or unparseable output
raises ParseError — there is no rule-based fallback.
"""

import json
from unittest.mock import patch, AsyncMock

import pytest

from app.services.model import ModelError, validate_output
from app.services.todo_parser import ParseError, TODO_SCHEMA, parse_todos


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
class TestParseTodosLLM:
    """Parsing always calls the LLM; failures raise ParseError (no fallback)."""

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
            assert result["degraded_reason"] is None
            assert len(result["candidates"]) == 1

    async def test_llm_model_error_raises(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = ModelError("timeout")
            with pytest.raises(ParseError):
                await parse_todos(
                    "明天开会，后天交报告",
                    llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
                )

    async def test_llm_invalid_json_raises(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "not json at all"
            with pytest.raises(ParseError):
                await parse_todos(
                    "明天开会",
                    llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
                )

    async def test_llm_empty_todos_returns_empty_no_fallback(self):
        with patch("app.services.todo_parser.chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = json.dumps({"todos": []})
            result = await parse_todos(
                "明天开会，后天交报告",
                llm_config={"api_key": "k", "base_url": "http://x", "model": "m"},
            )
            assert result["parser"] == "llm"
            assert result["candidates"] == []


@pytest.mark.asyncio
class TestParseTodosNoLLMConfig:
    """Without LLM config, parsing raises ParseError (no demo/rule fallback)."""

    async def test_no_llm_config_raises(self):
        with pytest.raises(ParseError):
            await parse_todos("今天开会，明天交报告")
