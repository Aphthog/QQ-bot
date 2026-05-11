"""
Unit tests for qq_bot.agent.runner — the ReAct agent loop.

All tests use a FakeLLM that returns preset ChatResponse objects in memory.
No real HTTP calls are made.
"""

import pytest

from qq_bot.agent.response import ChatResponse, ToolCall
from qq_bot.agent.runner import run, _sanitize_output
from qq_bot.config import settings


class FakeLLM:
    """In-memory LLM stub that cycles through a list of preset responses."""

    def __init__(self, responses: list[ChatResponse]):
        self.responses = responses
        self.call_count = 0
        self.last_kwargs: dict | None = None

    def supports_tools(self) -> bool:
        return True

    async def chat_with_tools(
        self,
        prompt,
        tools,
        context=None,
        *,
        system_prompt=None,
        image=None,
        model=None,
        tool_choice="auto",
        **kwargs,
    ):
        self.last_kwargs = {
            k: v for k, v in locals().items() if k != "self"
        }
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp


# ── helpers ──────────────────────────────────────────────────────────────

def _make_tool_call(id: str = "call_1", name: str = "get_weather") -> ToolCall:
    return ToolCall(id=id, name=name, arguments={"city": "上海"})


async def _fake_execute(tool_calls, ctx):
    """Mock tool executor — returns a canned result for every call."""
    results = []
    for tc in tool_calls:
        results.append(ToolCall.build_tool_result(tc.id, f"[mock result for {tc.name}]"))
    return results


# ── tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_runner_simple_reply_no_tools():
    """LLM returns text immediately — single call, no tool execution."""
    llm = FakeLLM([ChatResponse(text="你好！")])
    resp = await run(
        prompt="你好",
        image=None,
        context=[],
        system_prompt="你是一个助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "你好！"
    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_runner_one_tool_call_then_reply(monkeypatch):
    """LLM calls a tool once, then returns text on the next iteration."""
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls",
        _fake_execute,
    )

    tc = _make_tool_call()
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
        ChatResponse(text="上海今天晴天，25度"),
    ])
    resp = await run(
        prompt="上海天气",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "上海今天晴天，25度"
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_runner_max_iter_cap(monkeypatch):
    """LLM calls tools repeatedly; on the final iteration tool_choice is 'none'."""
    monkeypatch.setattr(settings, "AGENT_MAX_ITER", 3)
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls",
        _fake_execute,
    )

    tc = _make_tool_call()
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
        ChatResponse(tool_calls=[tc]),
        ChatResponse(text="最终回复"),
    ])
    resp = await run(
        prompt="复杂问题",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "最终回复"
    assert llm.call_count == 3
    assert llm.last_kwargs["tool_choice"] == "none"


@pytest.mark.asyncio
async def test_runner_llm_exception():
    """LLM raises an exception — runner returns fallback instead of crashing."""
    llm = FakeLLM([ChatResponse(text="你好")])

    async def failing(*args, **kwargs):
        raise RuntimeError("LLM connection error")

    llm.chat_with_tools = failing
    resp = await run(
        prompt="你好",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert "我好像卡住了" in resp.text


@pytest.mark.asyncio
async def test_runner_no_text_no_tools():
    """LLM returns neither text nor tool_calls — fallback is returned."""
    llm = FakeLLM([ChatResponse(text=None, tool_calls=None)])
    resp = await run(
        prompt="你好",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert "小脑袋卡住了" in resp.text


@pytest.mark.asyncio
async def test_runner_sanitize_output():
    """Output containing an API key pattern is replaced with a sanitized message."""
    llm = FakeLLM([ChatResponse(text="我的密钥是 sk-abc123def456ghi7890123456，请保管好")])
    resp = await run(
        prompt="你好",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "啊呀刚才走神了，再说点别的呗"
