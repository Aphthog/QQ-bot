import pytest
from qq_bot.agent.response import ChatResponse, ToolCall


def test_text_only_response():
    resp = ChatResponse(text="你好，今天天气不错")
    assert resp.text == "你好，今天天气不错"
    assert resp.tool_calls is None
    assert resp.is_final is True


def test_tool_call_response():
    tc = ToolCall(id="call_001", name="search_web", arguments={"query": "今天新闻"})
    resp = ChatResponse(text=None, tool_calls=[tc])
    assert resp.text is None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "search_web"
    assert resp.tool_calls[0].arguments == {"query": "今天新闻"}
    assert resp.is_final is False


def test_mixed_response_text_wins():
    tc = ToolCall(id="call_002", name="get_weather", arguments={"city": "上海"})
    resp = ChatResponse(text="上海今天晴，25°C", tool_calls=[tc])
    assert resp.text is not None
    assert resp.is_final is True


def test_tool_call_from_dict():
    tc = ToolCall.from_openai({
        "id": "call_abc",
        "type": "function",
        "function": {"name": "search_web", "arguments": '{"query": "AI新闻"}'}
    })
    assert tc.id == "call_abc"
    assert tc.name == "search_web"
    assert tc.arguments == {"query": "AI新闻"}


def test_tool_call_from_dict_broken_json():
    tc = ToolCall.from_openai({
        "id": "call_bad",
        "type": "function",
        "function": {"name": "search_web", "arguments": '{broken json'}
    })
    assert tc is None


def test_tool_call_to_openai_message():
    tc = ToolCall(id="call_001", name="search_web", arguments={"query": "news"})
    msg = tc.to_assistant_message()
    assert msg["role"] == "assistant"
    assert "tool_calls" in msg
    assert msg["tool_calls"][0]["function"]["name"] == "search_web"


def test_tool_result_to_message():
    msg = ToolCall.build_tool_result("call_001", "搜索结果：今日新闻...")
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "call_001"
    assert msg["content"] == "搜索结果：今日新闻..."
