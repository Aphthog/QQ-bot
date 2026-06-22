"""AgentLoop: main orchestrator binding Router, Planner, Executor, Reflector, Builder."""
from __future__ import annotations

import logging
from typing import Any

from qq_bot.agent.builder import Builder
from qq_bot.agent.bus import MessageBus
from qq_bot.agent.executor import Executor
from qq_bot.agent.planner import Planner
from qq_bot.agent.reflector import Reflector, ReflectResult
from qq_bot.agent.router import Router
from qq_bot.agent.state import AgentState, Intent
from qq_bot.tools.registry import ToolRegistry

logger = logging.getLogger("qq_bot.agent")


class AgentLoop:
    """Self-contained agent. One AgentLoop = one bot personality.

    V2 runs in single-agent mode (bus=None). Pass a MessageBus to enable
    multi-agent communication in the future.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        llm: Any,
        bus: MessageBus | None = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm
        self.bus = bus

    async def run(
        self,
        text: str,
        *,
        images: list[bytes] | None = None,
        memory_context: str = "",
        user_id: str = "",
        group_id: str = "",
    ) -> str:
        """Process a user message and return the bot's response text."""
        ctx = {"user_id": user_id, "group_id": group_id}

        # 1. Route
        intent = await Router.classify(text, self.llm, has_image=bool(images))

        if intent == Intent.COMMAND:
            return await self._handle_command(text, ctx)
        if intent == Intent.ADMIN:
            return await self._handle_admin(text, ctx)
        if intent == Intent.CHAT:
            return await Builder.build(text, AgentState(), self.llm, self.name, memory_context)

        # 2. Task → Agent Loop
        tool_schemas = ToolRegistry.get_all_schemas(for_user=True)
        plan, error = await Planner.decompose(text, self.llm, tool_schemas, memory_context)

        if error:
            return error
        if plan is None:
            return await Builder.build(text, AgentState(), self.llm, self.name, memory_context)

        # 3. Execute → Reflect loop
        state = AgentState(intent=Intent.TASK, plan=plan)
        completed: set[int] = set()

        while True:
            exec_state = await Executor.execute_plan(plan, completed, ctx)
            state.tool_results.extend(exec_state.tool_results)

            if len(completed) >= len(plan.steps):
                break

            result = await Reflector.evaluate(state, self.llm)
            if result == ReflectResult.DONE:
                break
            elif result == ReflectResult.REPLAN:
                plan, error = await Planner.decompose(text, self.llm, tool_schemas, memory_context)
                if error or plan is None:
                    break
                state.plan = plan
                completed.clear()
                state.retry_count += 1
                continue
            elif result == ReflectResult.RETRY:
                state.retry_count += 1
                if state.retry_count >= 3:
                    break

        # 4. Build final response
        return await Builder.build(text, state, self.llm, self.name, memory_context)

    async def _handle_command(self, text: str, ctx: dict) -> str:
        return await Builder.build(text, AgentState(), self.llm, self.name)

    async def _handle_admin(self, text: str, ctx: dict) -> str:
        return "管理员功能开发中～"

    async def _on_peer_message(self, msg: Any) -> None:
        pass
