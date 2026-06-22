"""Router: intent classification via lightweight LLM call."""
from __future__ import annotations

import json
import logging
from typing import Any

from qq_bot.agent.state import Intent
from qq_bot.llm.base import build_messages

logger = logging.getLogger("qq_bot.agent.router")

ROUTER_SYSTEM_PROMPT = """你是一个意图分类器。分析用户消息，输出 JSON：{"intent": "<类型>"}

意图类型：
- chat: 闲聊、打招呼、简单的图片理解（如"这梗图啥意思"）、不需要外部信息的普通对话
- task: 需要搜索、计算、生图、或任何需要工具/多步推理的请求。模棱两可时优先归为 task
- command: 以 / 开头的固定指令（/top, /memory 等）
- admin: 管理员管理操作（/ban, /whitelist, /config 等）

只输出JSON，不要其他文字。"""


class Router:
    @staticmethod
    def _parse_intent(raw: str) -> Intent:
        raw = raw.strip()
        # Extract JSON from possible markdown code blocks
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) >= 3 else raw
        try:
            data = json.loads(raw)
            intent_str = data.get("intent", "chat")
            return Intent(intent_str)
        except (json.JSONDecodeError, ValueError):
            return Intent.CHAT

    @staticmethod
    async def classify(
        text: str,
        llm: Any,  # LLMProvider
        has_image: bool = False,
    ) -> Intent:
        """Classify user message intent. Single lightweight LLM call."""
        messages = build_messages(
            system_prompt=ROUTER_SYSTEM_PROMPT,
            user_text=text,
        )
        try:
            raw = await llm.chat(messages, max_tokens=50, temperature=0.1)
            intent = Router._parse_intent(raw)
            logger.debug(f"Router: '{text[:50]}...' → {intent.value}")
            return intent
        except Exception:
            logger.error("Router LLM call failed, defaulting to chat", exc_info=True)
            return Intent.CHAT
