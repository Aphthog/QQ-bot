"""LLM Provider Protocol."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM backends must implement."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Send messages and return text response."""
        ...

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: str = "auto",
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send messages with tools, return raw API response dict with
        `content` (str|None) and `tool_calls` (list[dict]|None)."""
        ...

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text response chunks."""
        ...

    def supports_tools(self) -> bool:
        """Does this provider support function calling?"""
        ...

    def supports_images(self) -> bool:
        """Does this provider support image inputs?"""
        ...


def build_messages(
    system_prompt: str,
    history: list[dict[str, Any]] | None = None,
    user_text: str | None = None,
    user_images: list[bytes] | None = None,
) -> list[dict[str, Any]]:
    """Build OpenAI-compatible message list from components.

    Returns a list suitable for passing to any LLMProvider.
    """
    msgs: list[dict[str, Any]] = []

    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})

    if history:
        msgs.extend(history)

    if user_text is not None or user_images:
        content: list[dict[str, Any]] = []
        if user_text:
            content.append({"type": "text", "text": user_text})
        if user_images:
            import base64
            for img in user_images:
                b64 = base64.b64encode(img).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
        msgs.append({"role": "user", "content": content})

    return msgs
