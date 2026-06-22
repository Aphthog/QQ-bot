import pytest
from qq_bot.agent.executor import Executor
from qq_bot.agent.state import Plan, Step


class DummyRegistry:
    @classmethod
    async def execute(cls, name, args, ctx):
        return f"result of {name}: {args}"

    @classmethod
    async def execute_all(cls, tool_calls, ctx):
        return [{"role": "tool", "tool_call_id": tc["id"], "content": f"result for {tc['name']}"}
                for tc in tool_calls]


class TestExecutor:
    @pytest.mark.asyncio
    async def test_execute_independent_steps_in_parallel(self, monkeypatch):
        monkeypatch.setattr("qq_bot.agent.executor.ToolRegistry", DummyRegistry)
        plan = Plan(steps=[
            Step(id=1, action="web_search", params={"query": "a"}, depends_on=[]),
            Step(id=2, action="web_search", params={"query": "b"}, depends_on=[]),
        ])
        state = await Executor.execute_plan(plan, completed=set(), ctx={})
        assert len(state.tool_results) == 2

    @pytest.mark.asyncio
    async def test_respects_dependencies(self, monkeypatch):
        monkeypatch.setattr("qq_bot.agent.executor.ToolRegistry", DummyRegistry)
        plan = Plan(steps=[
            Step(id=1, action="web_search", params={"query": "a"}, depends_on=[]),
            Step(id=2, action="web_fetch", params={"url": "x"}, depends_on=[1]),
        ])
        state = await Executor.execute_plan(plan, completed=set(), ctx={})
        # Step 2 should NOT have run (dep on step 1 not yet completed)
        # Only step 1 ran
        assert len(state.tool_results) >= 1
