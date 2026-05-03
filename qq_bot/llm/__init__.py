from qq_bot.config import settings
from .base import BaseLLMAdapter
from .longcat import LongCatAdapter
from .ollama import OllamaAdapter
from .deepseek import DeepSeekAdapter

_adapters = {
    "longcat": LongCatAdapter,
    "ollama": OllamaAdapter,
    "deepseek": DeepSeekAdapter,
}


def get_adapter(provider: str = "") -> BaseLLMAdapter:
    provider = provider or settings.LLM_PROVIDER
    cls = _adapters.get(provider)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return cls()
