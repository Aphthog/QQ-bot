import httpx
import os
import base64
from typing import AsyncGenerator
from .base import BaseLLMAdapter


class LongCatAdapter(BaseLLMAdapter):
    """龙猫 (LongCat-Flash-Omni-2603) 适配器，支持文字+图片理解"""

    def __init__(self):
        self.api_key = os.getenv("LONGCAT_API_KEY", "")
        self.model = os.getenv("LONGCAT_MODEL", "LongCat-Flash-Omni-2603")
        self.base_url = os.getenv("LONGCAT_BASE_URL", "https://api.longcat.chat/openai/v1")

    def _build_message_content(self, prompt: str, image: bytes | None = None) -> list[dict]:
        """构建龙猫 API 格式的 content（列表形式）"""
        blocks = [{"type": "text", "text": prompt}]
        if image:
            img_b64 = base64.b64encode(image).decode()
            blocks.append({
                "type": "input_image",
                "input_image": {"type": "base64", "data": [img_b64]}
            })
        return blocks

    def _format_message(self, role: str, content) -> dict:
        """格式化消息，支持 list content（龙猫格式）或 string content

        注意：assistant 消息必须是纯字符串，不支持列表格式。
        """
        if isinstance(content, str):
            if role == "assistant":
                return {"role": role, "content": content}
            return {"role": role, "content": [{"type": "text", "text": content}]}
        else:
            return {"role": role, "content": content}

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
            messages.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})
        if context:
            # context 里的消息可能是 dict 或 string content
            for m in context:
                if isinstance(m.get("content"), list):
                    messages.append(m)
                elif isinstance(m.get("content"), str):
                    messages.append(self._format_message(m["role"], m["content"]))
                else:
                    messages.append(m)
        messages.append({"role": "user", "content": self._build_message_content(prompt, image)})

        payload: dict = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
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
        system_prompt: str | None = None,
        image: bytes | None = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
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

        payload: dict = {
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
