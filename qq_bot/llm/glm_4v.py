"""GLM-4.6V provider via Zhipu AI API."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from qq_bot.config import config

logger = logging.getLogger("qq_bot.llm.glm")


class GLM4VProvider:
    """GLM-4.6V multimodal provider with native tool calling."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
    ):
        self.api_key = api_key or config.GLM_API_KEY
        self.model = model or config.GLM_MODEL
        self.base_url = base_url or config.GLM_BASE_URL

    def supports_tools(self) -> bool:
        return True

    def supports_images(self) -> bool:
        return True

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        return payload

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        choice = data["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        raw_calls = msg.get("tool_calls") or []
        tool_calls = None
        if raw_calls:
            tool_calls = []
            for tc in raw_calls:
                func = tc.get("function", {})
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "arguments": args,
                })
        return {"content": content or None, "tool_calls": tool_calls}

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        payload = self._build_payload(
            messages, max_tokens=max_tokens, temperature=temperature,
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            result = self._parse_response(resp.json())
            return result["content"] or ""

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: str = "auto",
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            messages, tools=tools, tool_choice=tool_choice, max_tokens=max_tokens,
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            return self._parse_response(resp.json())

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        payload = self._build_payload(messages, max_tokens=max_tokens)
        payload["stream"] = True
        headers = self._auth_headers()
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line and line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
