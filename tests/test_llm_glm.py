import pytest
from qq_bot.llm.glm_4v import GLMProvider
from qq_bot.llm.base import build_messages


class TestGLMProvider:
    def test_supports_tools(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        assert p.supports_tools() is True

    def test_supports_images(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        assert p.supports_images() is True

    def test_build_request_payload_no_tools(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        msgs = build_messages("You are helpful.", user_text="Hi")
        payload = p._build_payload(msgs, max_tokens=100)
        assert payload["model"] == "glm-4.6v"
        assert len(payload["messages"]) == 2
        assert "tools" not in payload  # no tools when enable_search=False

    def test_build_request_payload_with_tools(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        msgs = build_messages("You are helpful.", user_text="Search for cats")
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        payload = p._build_payload(msgs, tools=tools, max_tokens=512, enable_search=True)
        assert payload["tools"] == tools + [{"type": "web_search", "web_search": {"enable": True}}]
        assert payload["tool_choice"] == "auto"

    def test_build_request_payload_without_search(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        msgs = build_messages("You are helpful.", user_text="Search for cats")
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        payload = p._build_payload(msgs, tools=tools, max_tokens=512)
        assert payload["tools"] == tools  # no web_search appended

    def test_parse_tool_call_response(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        raw = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"q":"cats"}'},
                    }],
                }
            }]
        }
        result = p._parse_response(raw)
        assert result["content"] is None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "search"

    def test_parse_text_response(self):
        p = GLMProvider(api_key="test", model="glm-4.6v")
        raw = {
            "choices": [{
                "message": {"content": "Hello!", "tool_calls": None},
            }]
        }
        result = p._parse_response(raw)
        assert result["content"] == "Hello!"
        assert result["tool_calls"] is None
