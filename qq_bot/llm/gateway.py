"""LLM Gateway — provider registry and lazy instantiation."""
from __future__ import annotations

from qq_bot.config import config
from qq_bot.llm.base import LLMProvider


class LLMGateway:
    """Factory for LLM providers. Add new providers here."""

    _providers: dict[str, type[LLMProvider]] = {}
    _instances: dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[LLMProvider]) -> None:
        cls._providers[name] = provider_cls

    @classmethod
    def get(cls, name: str = "") -> LLMProvider:
        name = name or config.LLM_PROVIDER
        if name not in cls._instances:
            if name not in cls._providers:
                raise ValueError(f"Unknown LLM provider: {name}")
            cls._instances[name] = cls._providers[name]()
        return cls._instances[name]


# Register built-in providers
from qq_bot.llm.glm_4v import GLMProvider  # noqa: E402

LLMGateway.register("glm", GLMProvider)
