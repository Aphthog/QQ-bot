from qq_bot.agent.state import AgentState, Plan, Step, Intent


class TestAgentState:
    def test_initial_state(self):
        state = AgentState()
        assert state.intent == Intent.UNKNOWN
        assert state.plan is None
        assert state.tool_results == []
        assert state.retry_count == 0
        assert state.final_text is None

    def test_plan_serialization(self):
        plan = Plan(steps=[
            Step(id=1, action="web_search", params={"query": "test"}, depends_on=[]),
            Step(id=2, action="web_fetch", params={"url": "http://x.com"}, depends_on=[1]),
        ])
        d = plan.to_dict()
        restored = Plan.from_dict(d)
        assert len(restored.steps) == 2
        assert restored.steps[0].action == "web_search"

    def test_step_is_ready(self):
        step = Step(id=1, action="search", params={"q": "x"}, depends_on=[])
        assert step.is_ready(completed_step_ids=set())

        step2 = Step(id=2, action="fetch", params={}, depends_on=[1])
        assert not step2.is_ready(completed_step_ids=set())
        assert step2.is_ready(completed_step_ids={1})

    def test_agent_state_to_dict_roundtrip(self):
        state = AgentState(
            intent=Intent.TASK,
            plan=Plan(steps=[Step(id=1, action="search", params={"q": "x"}, depends_on=[])]),
            tool_results=[{"role": "tool", "tool_call_id": "1", "content": "result"}],
            retry_count=0,
            final_text=None,
        )
        d = state.to_dict()
        restored = AgentState.from_dict(d)
        assert restored.intent == Intent.TASK
        assert restored.plan.steps[0].action == "search"
