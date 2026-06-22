import json
import pytest
from qq_bot.agent.planner import Planner, PLANNER_SYSTEM_PROMPT


class TestPlanner:
    def test_system_prompt_not_empty(self):
        assert len(PLANNER_SYSTEM_PROMPT) > 0
        assert "json" in PLANNER_SYSTEM_PROMPT.lower()

    def test_parse_valid_plan(self):
        raw = """{
            "steps": [
                {"id": 1, "action": "web_search", "params": {"query": "天气"}, "depends_on": []},
                {"id": 2, "action": "web_fetch", "params": {"url": "http://x.com"}, "depends_on": [1]}
            ]
        }"""
        plan = Planner._parse_plan(raw)
        assert plan is not None
        assert len(plan.steps) == 2
        assert plan.steps[0].action == "web_search"

    def test_rejects_too_many_steps(self):
        steps = [{"id": i, "action": f"step_{i}", "params": {}, "depends_on": []} for i in range(1, 7)]
        raw = json.dumps({"steps": steps})
        plan = Planner._parse_plan(raw, max_steps=5)
        assert plan is None  # should return None for >5 steps

    def test_parse_invalid_json(self):
        plan = Planner._parse_plan("garbage")
        assert plan is None

    def test_parse_empty_steps(self):
        plan = Planner._parse_plan('{"steps": []}')
        assert plan is None

    def test_parse_honest_fallback(self):
        raw = "这个任务太复杂了，请分步问我"
        plan = Planner._parse_plan(raw)
        assert plan is None
