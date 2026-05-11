from typing import AsyncGenerator

import httpx

from qq_bot.agent.response import ChatResponse, ToolCall
from qq_bot.config import settings
from .base import BaseLLMAdapter


class DeepSeekAdapter(BaseLLMAdapter):
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.model = settings.DEEPSEEK_MODEL
        self.base_url = "https://api.deepseek.com"

    def supports_tools(self) -> bool:
        return True

    def _build_messages(
        self,
        prompt: str | None,
        context: list[dict] | None,
        system_prompt: str | None,
        image: bytes | None,
    ) -> list[dict]:
        import base64

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.extend(context)
        # ENG REVIEW FIX: only add user message when prompt is provided
        # (tool results serve as the input via context)
        if prompt:
            user_content: list[dict] = [{"type": "text", "text": prompt}]
            if image:
                img_b64 = base64.b64encode(image).decode()
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                })
            messages.append({"role": "user", "content": user_content})
        return messages

    async def chat(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        model: str | None = None,
        **kwargs,
    ) -> str:
        resp = await self.chat_with_tools(
            prompt=prompt, tools=[], context=context,
            system_prompt=system_prompt, image=image, model=model,
            tool_choice="none", **kwargs,
        )
        return resp.text or ""

    async def chat_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        model: str | None = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> ChatResponse:
        messages = self._build_messages(prompt, context, system_prompt, image)

        payload: dict = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
            payload["temperature"] = 1.0
            payload["top_p"] = 1.0
        max_tokens = kwargs.get("max_tokens")
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        elif tools:
            payload["max_tokens"] = settings.AGENT_MAX_TOKENS

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            # ENG REVIEW FIX: empty choices guard
            if not data.get("choices"):
                raise RuntimeError(f"DeepSeek returned empty choices (HTTP {resp.status_code})")

            choice = data["choices"][0]
            message = choice.get("message", {})

            text = message.get("content")
            raw_tool_calls = message.get("tool_calls", [])
            tool_calls = []
            for raw in raw_tool_calls:
                tc = ToolCall.from_openai(raw)
                if tc:
                    tool_calls.append(tc)

            return ChatResponse(text=text or None, tool_calls=tool_calls or None)

    async def chat_stream(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        import json

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        payload = {"model": self.model, "messages": messages, "stream": True}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    if line and line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("choices"):
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
