import pytest
from qq_bot.llm.gateway import LLMGateway
from qq_bot.llm.glm_4v import GLM4VProvider


class TestLLMGateway:
    def test_get_provider_glm(self, monkeypatch):
        monkeypatch.setenv("GLM_API_KEY", "test-key")
        provider = LLMGateway.get("glm")
        assert isinstance(provider, GLM4VProvider)
        assert provider.supports_tools() is True

    def test_get_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMGateway.get("nonexistent")

    def test_get_default(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "glm")
        monkeypatch.setenv("GLM_API_KEY", "test-key")
        provider = LLMGateway.get()
        assert isinstance(provider, GLM4VProvider)
