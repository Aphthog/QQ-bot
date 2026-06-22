"""Executor: run tool calls from a Plan, respecting dependencies."""
from __future__ import annotations

import logging
from typing import Any

from qq_bot.agent.state import AgentState, Plan
from qq_bot.tools.registry import ToolRegistry

logger = logging.getLogger("qq_bot.agent.executor")


class Executor:
    @staticmethod
    async def execute_plan(
        plan: Plan,
        completed: set[int],
        ctx: dict[str, Any],
    ) -> AgentState:
        """Execute all ready steps from the plan in parallel.

        A step is "ready" if all its dependencies are in `completed`.
        Returns AgentState with appended tool_results.
        """
        ready = [s for s in plan.steps if s.is_ready(completed)]

        if not ready:
            return AgentState(plan=plan, tool_results=[])

        tool_calls = [
            {
                "id": f"call_{s.id}",
                "name": s.action,
                "arguments": s.params,
            }
            for s in ready
        ]

        logger.debug(f"Executor: running {len(tool_calls)} tool calls")
        results = await ToolRegistry.execute_all(tool_calls, ctx)

        # Mark executed steps as completed
        for s in ready:
            completed.add(s.id)

        return AgentState(plan=plan, tool_results=list(results))
