"""Planner: decompose user task into a Plan of Steps via LLM."""
from __future__ import annotations

import json
import logging
from typing import Any

from qq_bot.agent.state import Plan, Step
from qq_bot.config import config
from qq_bot.llm.base import build_messages

logger = logging.getLogger("qq_bot.agent.planner")

PLANNER_SYSTEM_PROMPT = """你是一个任务规划器。将用户请求分解为步骤序列，输出JSON。

可用工具：
- web_search(query): 搜索互联网
- web_fetch(url): 抓取网页内容
- run_code(code): 执行Python代码

输出格式：
{"steps": [{"id": 1, "action": "工具名", "params": {...}, "depends_on": []}]}

规则：
- 每个步骤只调用一个工具
- depends_on 是依赖的步骤ID列表
- 最多{max_steps}步。超过则回复"这个任务太复杂了，请分步问我吧"
- 如果不需要工具（闲聊），输出空steps数组

只输出JSON，不要其他文字。"""


class Planner:
    @staticmethod
    def _parse_plan(raw: str, max_steps: int | None = None) -> Plan | None:
        max_steps = max_steps or config.AGENT_MAX_PLAN_STEPS
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) >= 3 else raw
        try:
            data = json.loads(raw)
            steps_data = data.get("steps", [])
            if not steps_data:
                return None
            if len(steps_data) > max_steps:
                return None
            steps = [Step.from_dict(s) for s in steps_data]
            return Plan(steps=steps, condition=data.get("condition"))
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    @staticmethod
    async def decompose(
        text: str,
        llm: Any,
        tool_schemas: list[dict],
        context: str = "",
    ) -> tuple[Plan | None, str | None]:
        """Return (Plan, error_message). Error message is user-facing when plan fails."""
        prompt = PLANNER_SYSTEM_PROMPT.format(max_steps=config.AGENT_MAX_PLAN_STEPS)
        user_text = text
        if context:
            user_text = f"{text}\n\n可用上下文（群聊历史/记忆）：\n{context}"

        messages = build_messages(system_prompt=prompt, user_text=user_text)

        try:
            raw = await llm.chat(messages, max_tokens=512, temperature=0.3)
            plan = Planner._parse_plan(raw)
            if plan is None:
                if "复杂" in raw or "分步" in raw:
                    return None, "这个任务太复杂了，请分步问我吧～"
                return None, None  # empty steps = just respond
            logger.debug(f"Planner: {len(plan.steps)} steps")
            return plan, None
        except Exception:
            logger.error("Planner LLM call failed", exc_info=True)
            return None, "小脑袋卡住了，换个方式试试～"
