import pytest
from qq_bot.agent.builder import Builder, BUILDER_SYSTEM_PROMPT


class TestBuilder:
    def test_system_prompt_not_empty(self):
        assert len(BUILDER_SYSTEM_PROMPT) > 0
        assert "assistant" in BUILDER_SYSTEM_PROMPT.lower() or "助手" in BUILDER_SYSTEM_PROMPT
