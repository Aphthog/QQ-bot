"""
ReAct agent loop runner.

Drives the tool-calling loop: call LLM, execute tools, accumulate messages,
repeat until the model produces a text reply or the iteration cap is hit.
"""

from __future__ import annotations

import json
import logging
import re

from qq_bot.agent.response import ChatResponse
from qq_bot.agent.tools import execute_tool_calls
from qq_bot.config import settings
from qq_bot.security.rules import OUTPUT_SENSITIVE_PATTERNS

logger = logging.getLogger("qq_bot.agent")


def _sanitize_output(text: str) -> str:
    """Scan output against sensitive patterns; replace if any match."""
    if not text:
        return text
    for pattern in OUTPUT_SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return "啊呀刚才走神了，再说点别的呗"
    return text


async def run(
    prompt: str,
    image: bytes | None,
    context: list[dict],
    system_prompt: str,
    tools: list[dict],
    llm,
    events_context: dict,
) -> ChatResponse:
    """Run the ReAct agent loop.

    Parameters
    ----------
    prompt:
        User input (only passed to the LLM on the first iteration).
    image:
        Optional image bytes (only passed on the first iteration).
    context:
        Prior conversation messages to seed the accumulator.
    system_prompt:
        System prompt string (always passed to every LLM call).
    tools:
        OpenAI-style tool schemas (empty on the final iteration to force text).
    llm:
        LLM adapter with ``chat_with_tools(...)``.
    events_context:
        Arbitrary dict forwarded to tool handlers (e.g. group_id, user_id).
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if context:
        messages.extend(context)

    # messages[0] is system prompt if one was set, otherwise first context msg
    ctx_start = 1 if system_prompt else 0
    max_iter = settings.AGENT_MAX_ITER
    fallback = ChatResponse(text="啊呀，小脑袋卡住了，换个方式试试~")

    for iteration in range(1, max_iter + 1):
        should_force_reply = (iteration == max_iter)

        try:
            resp = await llm.chat_with_tools(
                prompt=prompt if iteration == 1 else None,
                tools=[] if should_force_reply else tools,
                context=messages[ctx_start:] if len(messages) > ctx_start else None,
                system_prompt=system_prompt,
                image=image if iteration == 1 else None,
                max_tokens=settings.AGENT_MAX_TOKENS,
                tool_choice="none" if should_force_reply else "auto",
            )
        except Exception:
            logger.error(
                "LLM call failed on iteration %d",
                iteration,
                exc_info=True,
            )
            return ChatResponse(text="我好像卡住了，过会儿再试试")

        if resp.text:
            return ChatResponse(text=_sanitize_output(resp.text))

        if resp.tool_calls:
            try:
                tool_results = await execute_tool_calls(resp.tool_calls, events_context)
            except Exception:
                logger.error(
                    "Tool execution failed on iteration %d",
                    iteration,
                    exc_info=True,
                )
                return ChatResponse(text="我好像卡住了，过会儿再试试")

            # Single assistant message with all tool_calls (API contract)
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(
                                tc.arguments, ensure_ascii=False
                            ),
                        },
                    }
                    for tc in resp.tool_calls
                ],
            })
            messages.extend(tool_results)
            continue

        return fallback

    return fallback
