from dotenv import load_dotenv
load_dotenv()

from .base import BaseLLMAdapter
from .ollama import OllamaAdapter
from .longcat import LongCatAdapter

def get_adapter(provider: str = "ollama") -> BaseLLMAdapter:
    adapters = {
        "ollama": OllamaAdapter,
        "longcat": LongCatAdapter,
    }
    return adapters.get(provider, OllamaAdapter)()
