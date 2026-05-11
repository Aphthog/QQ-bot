from abc import ABC, abstractmethod
from typing import AsyncGenerator

from qq_bot.agent.response import ChatResponse


class BaseLLMAdapter(ABC):
    @abstractmethod
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
        """返回 AI 回复文本"""
        ...

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
        """带 function calling 的聊天，返回 ChatResponse（含 text 或 tool_calls）。

        默认实现将 tools 置空并调用 chat() 进行兼容；支持 tools 的子类应重写此方法。
        """
        text = await self.chat(
            prompt=prompt, context=context,
            system_prompt=system_prompt, image=image, model=model, **kwargs,
        )
        return ChatResponse(text=text)

    def supports_tools(self) -> bool:
        """默认 False，子类重写返回 True"""
        return False

    @abstractmethod
    async def chat_stream(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式返回"""
        ...
