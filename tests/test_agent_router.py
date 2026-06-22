import pytest
from qq_bot.agent.router import Router, ROUTER_SYSTEM_PROMPT
from qq_bot.agent.state import Intent


class TestRouter:
    def test_system_prompt_not_empty(self):
        assert len(ROUTER_SYSTEM_PROMPT) > 0
        assert "分类" in ROUTER_SYSTEM_PROMPT

    def test_parse_chat_response(self):
        result = Router._parse_intent('{"intent": "chat"}')
        assert result == Intent.CHAT

    def test_parse_task_response(self):
        result = Router._parse_intent('{"intent": "task"}')
        assert result == Intent.TASK

    def test_parse_command_response(self):
        result = Router._parse_intent('{"intent": "command"}')
        assert result == Intent.COMMAND

    def test_parse_invalid_json_falls_back_to_chat(self):
        result = Router._parse_intent("garbage")
        assert result == Intent.CHAT

    def test_parse_missing_key_falls_back_to_chat(self):
        result = Router._parse_intent('{"other": "value"}')
        assert result == Intent.CHAT

    def test_parse_empty_response(self):
        result = Router._parse_intent("")
        assert result == Intent.CHAT
