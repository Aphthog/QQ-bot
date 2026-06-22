"""Reflector: evaluate tool execution results and decide next action."""
from __future__ import annotations

import logging
from typing import Any

from qq_bot.agent.state import AgentState, ReflectResult
from qq_bot.config import config
from qq_bot.llm.base import build_messages

logger = logging.getLogger("qq_bot.agent.reflector")

REFLECTOR_SYSTEM_PROMPT = """你是一个结果评估器。检查工具执行结果，输出一个词：done / retry / replan。

- done: 所有信息已获取，可以回复用户
- retry: 工具返回了空或异常结果，换方式再试
- replan: 当前计划不对，需要重新规划

只输出一个词。"""


class Reflector:
    @staticmethod
    def _parse(raw: str) -> ReflectResult:
        raw = raw.strip().lower()
        if "retry" in raw:
            return ReflectResult.RETRY
        if "replan" in raw:
            return ReflectResult.REPLAN
        return ReflectResult.DONE

    @staticmethod
    async def evaluate(
        state: AgentState,
        llm: Any,
        max_retry: int | None = None,
    ) -> ReflectResult:
        """Evaluate tool results and return next action."""
        max_retry = max_retry if max_retry is not None else config.AGENT_MAX_RETRY

        if not state.tool_results:
            return ReflectResult.DONE

        # Quick check: any obvious failure?
        has_error = any(
            "失败" in r.get("content", "") or "异常" in r.get("content", "")
            for r in state.tool_results
        )

        if not has_error:
            return ReflectResult.DONE

        if state.retry_count >= max_retry:
            logger.debug(f"Reflector: max retry ({max_retry}) reached, giving up")
            return ReflectResult.DONE

        # Ask LLM
        results_text = "\n".join(
            f"[{r.get('tool_call_id', '?')}]: {r.get('content', '')}"
            for r in state.tool_results
        )
        messages = build_messages(
            system_prompt=REFLECTOR_SYSTEM_PROMPT,
            user_text=f"工具执行结果：\n{results_text}",
        )
        try:
            raw = await llm.chat(messages, max_tokens=20, temperature=0.1)
            result = Reflector._parse(raw)
            logger.debug(f"Reflector: {result.value}")
            return result
        except Exception:
            logger.error("Reflector LLM call failed, defaulting to done", exc_info=True)
            return ReflectResult.DONE
