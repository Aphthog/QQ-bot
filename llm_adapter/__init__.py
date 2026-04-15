from dotenv import load_dotenv
load_dotenv()

from .base import BaseLLMAdapter
from .ollama import OllamaAdapter
from .deepseek import DeepSeekAdapter

def get_adapter(provider: str = "ollama") -> BaseLLMAdapter:
    adapters = {
        "ollama": OllamaAdapter,
        "deepseek": DeepSeekAdapter,
    }
    return adapters.get(provider, OllamaAdapter)()
