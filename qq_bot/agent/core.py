"""AgentLoop: unified tool-calling loop — one LLM call handles chat + search."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from qq_bot.agent.bus import MessageBus
from qq_bot.config import config
from qq_bot.tools.registry import ToolRegistry

logger = logging.getLogger("qq_bot.agent")

# Cross-module channel for tools to pass image file paths back to the agent loop.
_pending_images: list[str] = []


# Commands detected by prefix, no LLM call needed
COMMANDS = {"/top", "/memory", "/help", "/status", "/ping"}

# Patterns that indicate Zhipu's built-in web_search timed out or failed
SEARCH_FAILURE_MARKERS = [
    "搜索工具超时", "搜索超时", "搜索失败", "无法搜索",
    "search timeout", "search failed",
]


def _is_search_failure(text: str) -> bool:
    return any(m in text for m in SEARCH_FAILURE_MARKERS)


async def _fallback_web_search(query: str) -> str | None:
    """Direct DuckDuckGo HTML search when Zhipu's built-in search fails."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"q": query}, headers=headers)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for el in soup.select(".result__snippet"):
                text = el.get_text(strip=True)
                if text:
                    results.append(text)
            return "\n".join(results[:5]) if results else None
    except Exception:
        return None


def _parse_text_tool_call(text: str) -> list[dict[str, Any]] | None:
    """Parse tool calls that the model emitted as text instead of native tool_calls."""
    # Try <tool_call>...</tool_call> wrapper first
    match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and "name" in data:
        return [{"id": "call_text_0", "name": data["name"], "arguments": data.get("arguments", {})}]
    if isinstance(data, list):
        return [
            {"id": f"call_text_{i}", "name": item["name"], "arguments": item.get("arguments", {})}
            for i, item in enumerate(data)
            if isinstance(item, dict) and "name" in item
        ] or None
    return None


def _is_garbage(text: str) -> bool:
    """Filter empty, whitespace-only, or pure-punctuation messages."""
    stripped = text.strip()
    if not stripped:
        return True
    # Pure punctuation/emoji without meaningful text
    if len(stripped) < 2 and not stripped.isalnum():
        return True
    return False


class AgentLoop:
    """Self-contained agent. One AgentLoop = one bot personality."""

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
        image_urls: list[str] | None = None,
        memory_context: str = "",
        user_id: str = "",
        group_id: str = "",
    ) -> dict[str, Any]:
        """Process a user message — single unified LLM call with tools + search.

        Returns ``{"text": str, "images": list[str]}`` where images is a list of
        absolute file paths ready for MessageSegment.image().
        """
        _pending_images.clear()

        ctx = {"user_id": user_id, "group_id": group_id}

        # Fast path: prefix commands
        stripped = text.strip()
        for cmd in COMMANDS:
            if stripped.startswith(cmd):
                return {"text": await self._handle_command(stripped), "images": []}

        # Garbage filter: empty/pure-punctuation without images → skip API call
        has_images = bool(images) or bool(image_urls)
        if not has_images and _is_garbage(text):
            return {"text": "", "images": []}

        text_result = await self._run_unified_loop(text, ctx, memory_context, image_urls or [])
        images_result = list(_pending_images)
        _pending_images.clear()
        return {"text": text_result, "images": images_result}

    async def _run_unified_loop(
        self,
        text: str,
        ctx: dict,
        memory_context: str = "",
        image_urls: list[str] | None = None,
    ) -> str:
        """Single LLM call. If the question needs search, LLM uses web_search.
        If it's just chat, LLM replies directly. One API round-trip for most cases."""
        tools = ToolRegistry.get_all_schemas(for_user=True)

        user_text = text
        if memory_context:
            user_text = (
                f"【当前问题】\n{text}\n\n"
                f"【最近的聊天记录 — 用于理解指代和话题延续】\n{memory_context}"
            )

        if image_urls:
            content_parts: list[dict[str, Any]] = [
                {"type": "text", "text": user_text}
            ]
            for url in image_urls:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": url},
                })
            user_content: Any = content_parts
        else:
            user_content = user_text

        unified_prompt = self.system_prompt

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": unified_prompt},
            {"role": "user", "content": user_content},
        ]

        max_rounds = config.AGENT_MAX_PLAN_STEPS
        for _ in range(max_rounds):
            try:
                result = await self.llm.chat_with_tools(
                    messages, tools=tools, max_tokens=config.MAX_RESPONSE_TOKENS,
                    enable_thinking=config.TASK_THINKING,
                )
            except Exception:
                logger.error("LLM call failed", exc_info=True)
                return "哎呀，小脑袋卡住了，换个方式试试～"

            content = result.get("content")
            tool_calls = result.get("tool_calls")

            # LLM returned text content — check it's not a leaked tool call
            if content and tool_calls is None:
                stripped = content.strip()
                if stripped.startswith("<tool_call>") or stripped.startswith("{"):
                    # Model emitted tool call as text — treat as tool call, don't show to user
                    tool_calls = _parse_text_tool_call(stripped)
                    content = None
                else:
                    if _is_search_failure(stripped):
                        fallback = await _fallback_web_search(text)
                        if fallback:
                            messages.append({"role": "assistant", "content": stripped})
                            messages.append({
                                "role": "user",
                                "content": f"[网络搜索结果]\n{fallback}\n\n基于以上搜索结果回答用户问题。",
                            })
                            continue
                        return "搜索暂时不可用，稍后再问我～"
                    return content
            if tool_calls is None:
                return "唔...我想了想还是没想明白～"

            # Execute locally-registered tools (web_fetch, run_code)
            local_calls = [tc for tc in tool_calls if tc["name"] in ToolRegistry._tools]
            if not local_calls:
                continue  # LLM used built-in web_search, loop for final answer

            results = await ToolRegistry.execute_all(local_calls, ctx)

            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ],
            })
            for r in results:
                messages.append({
                    "role": r.get("role", "tool"),
                    "tool_call_id": r.get("tool_call_id", ""),
                    "content": r.get("content", ""),
                })

        return "唔...想了半天还是没结果，换个问法试试？"

    async def _handle_command(self, text: str) -> str:
        cmd = text.strip().split()[0]
        if cmd == "/ping":
            return "pong!"
        if cmd == "/help":
            return "可用: /ping /status /top /memory"
        if cmd == "/status":
            return f"运行中 | 模型: {config.GLM_MODEL} | 思考: {'开' if config.TASK_THINKING else '关'}"
        if cmd == "/top":
            return "这个功能还在开发中～"
        if cmd == "/memory":
            return "这个功能还在开发中～"
        return f"未知命令: {cmd}"

    async def _on_peer_message(self, msg: Any) -> None:
        pass
