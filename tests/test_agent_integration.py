"""
Integration tests for the qq_bot ReAct agent loop.

Tests exercise the full agent pipeline: LLM calls, tool execution, result
accumulation, max-iteration caps, and error recovery.  All tests use
monkeypatch to mock ``execute_tool_calls`` so no real HTTP calls are made.
"""

import pytest

from qq_bot.agent.response import ChatResponse, ToolCall
from qq_bot.agent.runner import run
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


class FakeLLMNoTools:
    """Variant where supports_tools() returns False (simulating Ollama/LongCat fallback)."""

    def __init__(self, responses: list[ChatResponse]):
        self.responses = responses
        self.call_count = 0
        self.last_kwargs: dict | None = None

    def supports_tools(self) -> bool:
        return False

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
        results.append(
            ToolCall.build_tool_result(tc.id, f"[mock result for {tc.name}]")
        )
    return results


# ── tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_weather_integration(monkeypatch):
    """LLM calls get_weather, then replies with a text weather report."""
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _fake_execute
    )

    tc = _make_tool_call(name="get_weather")
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
        ChatResponse(text="上海今天晴天，25度"),
    ])
    resp = await run(
        prompt="上海天气",
        image=None,
        context=[],
        system_prompt="你是天气助手",
        tools=[],
        llm=llm,
        events_context={"group_id": "123"},
    )
    assert resp.text == "上海今天晴天，25度"
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_search_integration(monkeypatch):
    """LLM calls search_web, then replies with search-informed text."""
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _fake_execute
    )

    tc = ToolCall(id="call_s1", name="search_web", arguments={"query": "GPT-5"})
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
        ChatResponse(text="GPT-5 于 2025 年发布，支持多模态推理"),
    ])
    resp = await run(
        prompt="GPT-5最新消息",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "GPT-5 于 2025 年发布，支持多模态推理"
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_multitool_parallel_integration(monkeypatch):
    """LLM calls search_web AND get_weather in one response; both results processed."""
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _fake_execute
    )

    tc1 = ToolCall(id="call_a", name="search_web", arguments={"query": "上海天气"})
    tc2 = ToolCall(id="call_b", name="get_weather", arguments={"city": "上海"})
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc1, tc2]),
        ChatResponse(text="上海今天多云转晴，22度，适合出游"),
    ])
    resp = await run(
        prompt="上海天气怎么样",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "上海今天多云转晴，22度，适合出游"
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_max_iter_force_reply(monkeypatch):
    """On final iteration tools=[] and tool_choice='none' to force a text reply."""
    monkeypatch.setattr(settings, "AGENT_MAX_ITER", 3)
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _fake_execute
    )

    tc = _make_tool_call()
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
        ChatResponse(tool_calls=[tc]),
        ChatResponse(text="经过多次查询，最终答案是42"),
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
    assert resp.text == "经过多次查询，最终答案是42"
    assert llm.call_count == 3
    # Last call should force text: no tools, tool_choice="none"
    assert llm.last_kwargs["tools"] == []
    assert llm.last_kwargs["tool_choice"] == "none"


@pytest.mark.asyncio
async def test_unknown_tool_graceful(monkeypatch):
    """LLM calls a non-existent tool; executor returns error. Agent recovers."""

    async def _exec_with_unknown(tool_calls, ctx):
        results = []
        for tc in tool_calls:
            if tc.name == "bad_tool":
                results.append(
                    ToolCall.build_tool_result(tc.id, "[工具 'bad_tool' 不存在]")
                )
            else:
                results.append(
                    ToolCall.build_tool_result(tc.id, f"[mock result for {tc.name}]")
                )
        return results

    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _exec_with_unknown
    )

    tc = ToolCall(id="call_x", name="bad_tool", arguments={})
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
        ChatResponse(text="抱歉，那个工具不可用，我换个方式帮你"),
    ])
    resp = await run(
        prompt="用坏工具做点事",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "抱歉，那个工具不可用，我换个方式帮你"
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_tool_execution_exception_in_loop(monkeypatch):
    """execute_tool_calls raises an exception; runner returns fallback text."""

    async def _failing_execute(tool_calls, ctx):
        raise RuntimeError("工具执行异常")

    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _failing_execute
    )

    tc = _make_tool_call(name="get_weather")
    llm = FakeLLM([
        ChatResponse(tool_calls=[tc]),
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
    assert "我好像卡住了" in resp.text


@pytest.mark.asyncio
async def test_provider_fallback_no_tools(monkeypatch):
    """Provider without tool support still works — LLM returns text directly."""
    monkeypatch.setattr(
        "qq_bot.agent.runner.execute_tool_calls", _fake_execute
    )

    llm = FakeLLMNoTools([
        ChatResponse(text="你好，我是一个不支持 tools 的 LLM，但我可以正常聊天"),
    ])
    resp = await run(
        prompt="你好",
        image=None,
        context=[],
        system_prompt="你是助手",
        tools=[],
        llm=llm,
        events_context={},
    )
    assert resp.text == "你好，我是一个不支持 tools 的 LLM，但我可以正常聊天"
    assert llm.call_count == 1
    assert llm.supports_tools() is False
