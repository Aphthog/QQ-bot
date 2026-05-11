"""
Unit tests for qq_bot.agent.tools — tool schemas, handler registry, and executor.

All handler tests use MOCKED handlers (no real HTTP calls).
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from qq_bot.agent.tools import TOOL_SCHEMAS, TOOL_HANDLERS, execute_tool_calls
from qq_bot.agent.response import ToolCall
from qq_bot.config import settings


def test_all_schemas_have_required_fields():
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        func = schema["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"


def test_all_handlers_match_schemas():
    schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    handler_names = set(TOOL_HANDLERS.keys())
    assert schema_names == handler_names, (
        f"Mismatch: schemas={schema_names}, handlers={handler_names}"
    )


def test_tool_names_unique():
    names = [s["function"]["name"] for s in TOOL_SCHEMAS]
    assert len(names) == len(set(names)), f"Duplicate tool names: {names}"


@pytest.mark.asyncio
async def test_execute_known_tool():
    """Mock handler returns a known value."""
    tcs = [ToolCall(id="c1", name="search_web", arguments={"query": "天气"})]
    mock_handler = AsyncMock(return_value="搜索结果：今天晴")
    with patch.dict(TOOL_HANDLERS, {"search_web": mock_handler}):
        results = await execute_tool_calls(tcs, {})
    assert len(results) == 1
    assert results[0]["role"] == "tool"
    assert results[0]["tool_call_id"] == "c1"
    assert "搜索结果" in results[0]["content"]
    mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    tcs = [ToolCall(id="c2", name="nonexistent_tool", arguments={})]
    results = await execute_tool_calls(tcs, {})
    assert len(results) == 1
    assert "不存在" in results[0]["content"]


@pytest.mark.asyncio
async def test_execute_parallel():
    tcs = [
        ToolCall(id="c4", name="get_top_speakers", arguments={}),
        ToolCall(id="c5", name="random_mention", arguments={}),
    ]
    mock1 = AsyncMock(return_value="排行结果")
    mock2 = AsyncMock(return_value="@某人")
    with patch.dict(
        TOOL_HANDLERS,
        {"get_top_speakers": mock1, "random_mention": mock2},
    ):
        results = await execute_tool_calls(tcs, {"group_id": "12345"})
    assert len(results) == 2
    for r in results:
        assert r["role"] == "tool"
    assert "排行结果" in results[0]["content"]
    assert "@某人" in results[1]["content"]


@pytest.mark.asyncio
async def test_execute_tool_timeout():
    """Handler times out -> returns timeout message."""
    async def slow_handler(params, ctx):
        await asyncio.sleep(99)
        return "done"

    tcs = [ToolCall(id="c6", name="slow_tool", arguments={})]
    # Patch the timeout to a tiny value so the test completes instantly
    with patch.object(settings, "AGENT_TOOL_TIMEOUT", 0.01):
        with patch.dict(TOOL_HANDLERS, {"slow_tool": slow_handler}):
            results = await execute_tool_calls(tcs, {})
    assert len(results) == 1
    assert "超时" in results[0]["content"]


@pytest.mark.asyncio
async def test_execute_tool_exception():
    """Handler raises -> returns exception message."""
    async def failing_handler(params, ctx):
        raise RuntimeError("模拟错误")

    tcs = [ToolCall(id="c7", name="failing_tool", arguments={})]
    with patch.dict(TOOL_HANDLERS, {"failing_tool": failing_handler}):
        results = await execute_tool_calls(tcs, {})
    assert len(results) == 1
    assert "异常" in results[0]["content"]
