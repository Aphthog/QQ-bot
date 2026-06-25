"""Smoke test: verify the full agent pipeline can be imported and wired."""
import pytest


class TestIntegration:
    def test_all_modules_importable(self):
        from qq_bot.config import config
        from qq_bot.agent.core import AgentLoop
        from qq_bot.agent.state import AgentState, Intent, Plan, Step
        from qq_bot.agent.router import Router
        from qq_bot.agent.planner import Planner
        from qq_bot.agent.executor import Executor
        from qq_bot.agent.reflector import Reflector
        from qq_bot.agent.builder import Builder
        from qq_bot.agent.bus import MessageBus
        from qq_bot.llm.base import LLMProvider, build_messages
        from qq_bot.llm.glm_4v import GLMProvider
        from qq_bot.llm.gateway import LLMGateway
        from qq_bot.tools.registry import ToolRegistry, tool
        from qq_bot.memory.store import MemoryStore
        from qq_bot.memory.vector import VectorStore
        from qq_bot.memory.profile import ProfileManager
        from qq_bot.memory.manager import MemoryManager
        from qq_bot.access.guard import AccessGuard
        assert True

    def test_tools_are_registered(self):
        import qq_bot.tools.core  # noqa: F401
        schemas = __import__("qq_bot.tools.registry", fromlist=["ToolRegistry"]).ToolRegistry.get_all_schemas()
        assert len(schemas) >= 2  # core tools + any additional ones registered by other imports
        names = [s["function"]["name"] for s in schemas]
        assert "web_fetch" in names
        assert "run_code" in names

    def test_agent_loop_creatable(self):
        from qq_bot.agent.core import AgentLoop
        from qq_bot.llm.glm_4v import GLMProvider
        llm = GLMProvider(api_key="test", model="glm-4.6v")
        loop = AgentLoop(name="test", system_prompt="You are helpful.", llm=llm)
        assert loop.name == "test"
        assert loop.bus is None

    def test_message_bus_stub(self):
        from qq_bot.agent.bus import MessageBus, AgentMessage
        bus = MessageBus()
        msg = AgentMessage(sender="agent_a", content={"text": "hello"})
        assert msg.sender == "agent_a"
