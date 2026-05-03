import base64
from typing import AsyncGenerator

import httpx

from qq_bot.config import settings
from .base import BaseLLMAdapter


class LongCatAdapter(BaseLLMAdapter):
    """龙猫 (LongCat-Flash-Omni-2603) 适配器，支持文字+图片理解"""

    def __init__(self):
        self.api_key = settings.LONGCAT_API_KEY
        self.model = settings.LONGCAT_MODEL
        self.base_url = settings.LONGCAT_BASE_URL

    def _build_message_content(self, prompt: str, image: bytes | None = None) -> list[dict]:
        blocks = [{"type": "text", "text": prompt}]
        if image:
            img_b64 = base64.b64encode(image).decode()
            blocks.append({
                "type": "input_image",
                "input_image": {"type": "base64", "data": [img_b64]},
            })
        return blocks

    def _format_message(self, role: str, content) -> dict:
        if isinstance(content, str):
            if role == "assistant":
                return {"role": role, "content": content}
            return {"role": role, "content": [{"type": "text", "text": content}]}
        return {"role": role, "content": content}

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
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})
        if context:
            for m in context:
                if isinstance(m.get("content"), list):
                    messages.append(m)
                elif isinstance(m.get("content"), str):
                    messages.append(self._format_message(m["role"], m["content"]))
                else:
                    messages.append(m)
        messages.append({"role": "user", "content": self._build_message_content(prompt, image)})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": kwargs.get("max_tokens", 300),
            "topP": 0.9,
            "topK": 1,
            "textRepetitionPenalty": 1,
            "output_modalities": ["text"],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        import logging
        log = logging.getLogger("qq_bot.debug")
        if log.isEnabledFor(logging.DEBUG):
            import json as _json
            log.debug(f"LongCat payload:\n{_json.dumps(payload, ensure_ascii=False, indent=2)[:2000]}")
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            if resp.status_code != 200:
                log.error(f"LongCat API {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

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
            messages.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": self._build_message_content(prompt, image)})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "topP": 0.9,
            "topK": 1,
            "textRepetitionPenalty": 1,
            "output_modalities": ["text"],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
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
