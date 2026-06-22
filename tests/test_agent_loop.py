import pytest
from unittest.mock import AsyncMock, patch
from qq_bot.agent.core import AgentLoop
from qq_bot.agent.state import Intent, AgentState, Plan, Step


class TestAgentLoop:
    @pytest.mark.asyncio
    async def test_chat_intent_returns_text(self):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = '{"intent": "chat"}'

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)

        with patch("qq_bot.agent.core.Builder") as mock_builder:
            mock_builder.build = AsyncMock(return_value="你好呀！")
            result = await loop.run("你好")
            assert result == "你好呀！"

    @pytest.mark.asyncio
    async def test_task_intent_goes_through_plan_execute(self):
        mock_llm = AsyncMock()
        mock_llm.chat.side_effect = [
            '{"intent": "task"}',
            '{"steps": [{"id": 1, "action": "web_search", "params": {"query": "天气"}, "depends_on": []}]}',
            "done",
        ]

        loop = AgentLoop(name="test", system_prompt="You are test bot", llm=mock_llm)

        with patch("qq_bot.agent.core.Builder") as mock_builder, \
             patch("qq_bot.agent.core.Executor") as mock_executor:
            mock_builder.build = AsyncMock(return_value="今天天气不错")
            mock_executor.execute_plan = AsyncMock(return_value=AgentState(
                tool_results=[{"role": "tool", "tool_call_id": "call_1", "content": "晴天 25°C"}]
            ))

            result = await loop.run("今天天气怎么样")
            assert result == "今天天气不错"
