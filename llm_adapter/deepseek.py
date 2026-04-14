import httpx
from typing import AsyncGenerator
import os
from .base import BaseLLMAdapter


class DeepSeekAdapter(BaseLLMAdapter):
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.base_url = "https://api.deepseek.com"

    async def chat(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        image: bytes | None = None,
        model: str | None = None,
        **kwargs
    ) -> str:
        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        image: bytes | None = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                async for line in response.aiter_lines():
                    if line and line.startswith("data: "):
                        import json
                        try:
                            data = json.loads(line[6:])
                            if data.get("choices"):
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
