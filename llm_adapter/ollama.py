import httpx
from typing import AsyncGenerator
import os
from .base import BaseLLMAdapter


class OllamaAdapter(BaseLLMAdapter):
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llava")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))

    async def chat(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        model: str | None = None,
        **kwargs
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }
        if image:
            import base64
            payload["images"] = [base64.b64encode(image).decode()]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    async def chat_stream(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if image:
            import base64
            payload["images"] = [base64.b64encode(image).decode()]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue
