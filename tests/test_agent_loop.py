import pytest
from unittest.mock import AsyncMock, patch
from qq_bot.agent.core import (
    AgentLoop, _parse_text_tool_call, _is_search_failure, _is_garbage,
)


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_chat_reply_directly(self):
        """Simple chat: LLM replies with content, no tools needed."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "content": "你好呀！",
            "tool_calls": None,
        }

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        result = await loop.run("你好")
        assert result["text"] == "你好呀！"
        assert result["images"] == []
        assert mock_llm.chat_with_tools.called

    @pytest.mark.asyncio
    async def test_search_triggers_web_search(self):
        """Factual query: LLM uses web_search, then replies."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.side_effect = [
            {"content": None, "tool_calls": []},  # web_search runs server-side
            {"content": "今天北京晴，25°C", "tool_calls": None},
        ]

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        result = await loop.run("今天天气怎么样")
        assert result["text"] == "今天北京晴，25°C"
        assert result["images"] == []
        assert mock_llm.chat_with_tools.call_count == 2

    @pytest.mark.asyncio
    async def test_executes_local_tools(self):
        """LLM requests run_code tool, executes, gets result back."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "name": "run_code",
                    "arguments": {"code": "print(1+1)"},
                }],
            },
            {"content": "结果是2", "tool_calls": None},
        ]

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        result = await loop.run("计算1+1")
        assert result["text"] == "结果是2"
        assert result["images"] == []
        assert mock_llm.chat_with_tools.call_count == 2

    @pytest.mark.asyncio
    async def test_command_fast_path(self):
        """Commands like /ping skip LLM entirely."""
        mock_llm = AsyncMock()
        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        result = await loop.run("/ping")
        assert result["text"] == "pong!"
        assert result["images"] == []
        assert not mock_llm.chat_with_tools.called

    @pytest.mark.asyncio
    async def test_error_fallback(self):
        """LLM error returns friendly fallback."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.side_effect = Exception("API error")

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        result = await loop.run("你好")
        assert "卡住" in result["text"] or "试试" in result["text"]
        assert result["images"] == []


class TestParseTextToolCall:
    def test_parse_xml_wrapped(self):
        """Parse <tool_call>{"name": "web_search", ...}</tool_call> format."""
        text = '<tool_call>\n{"name": "web_search", "arguments": {"query": "天气"}}\n</tool_call>'
        result = _parse_text_tool_call(text)
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "web_search"
        assert result[0]["arguments"] == {"query": "天气"}

    def test_parse_bare_json(self):
        """Parse bare {"name": "...", "arguments": {...}} format."""
        text = '{"name": "run_code", "arguments": {"code": "1+1"}}'
        result = _parse_text_tool_call(text)
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "run_code"

    def test_parse_invalid_json_returns_none(self):
        """Invalid JSON returns None."""
        assert _parse_text_tool_call("hello world") is None

    def test_parse_json_without_name_returns_none(self):
        """JSON without 'name' field returns None."""
        assert _parse_text_tool_call('{"foo": "bar"}') is None


class TestSearchFailure:
    def test_detects_search_timeout(self):
        assert _is_search_failure("搜索工具超时了，不过...")
        assert _is_search_failure("搜索超时")
        assert _is_search_failure("search timeout, trying...")

    def test_normal_reply_not_detected(self):
        assert not _is_search_failure("今天天气不错")
        assert not _is_search_failure("你好呀！")

    @pytest.mark.asyncio
    async def test_fallback_triggers_on_search_failure(self):
        """When LLM says search timed out, fallback search runs and feeds results back."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.side_effect = [
            {"content": "搜索工具超时了，不过据我所知...", "tool_calls": None},
            {"content": "根据搜索，答案是42", "tool_calls": None},
        ]

        async def fake_fallback(query):
            return "搜索结果1\n搜索结果2"

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        with patch("qq_bot.agent.core._fallback_web_search", new=fake_fallback):
            result = await loop.run("今天天气怎么样")
        assert result["text"] == "根据搜索，答案是42"
        assert result["images"] == []
        assert mock_llm.chat_with_tools.call_count == 2

    @pytest.mark.asyncio
    async def test_fallback_unavailable_returns_polite_message(self):
        """When both search and fallback fail, return polite unavailable message."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "content": "搜索工具超时了",
            "tool_calls": None,
        }

        async def fake_fallback(query):
            return None  # fallback also failed

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)
        with patch("qq_bot.agent.core._fallback_web_search", new=fake_fallback):
            result = await loop.run("今天天气怎么样")
        assert "搜索暂时不可用" in result["text"]
        assert result["images"] == []
