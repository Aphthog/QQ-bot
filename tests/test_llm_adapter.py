"""
Test suite for LLM adapters (Ollama and DeepSeek).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
sys.path.insert(0, "/c/Users/Camille/Desktop/qq-bot")

from llm_adapter.base import BaseLLMAdapter


class TestOllamaAdapter:
    """Tests for OllamaAdapter."""

    @pytest.mark.asyncio
    async def test_ollama_adapter_chat(self, mock_ollama_response):
        """Test successful chat with Ollama adapter."""
        from llm_adapter.ollama import OllamaAdapter

        adapter = OllamaAdapter()

        mock_post = AsyncMock()
        mock_post.return_value = mock_ollama_response

        with patch("aiohttp.ClientSession.post", return_value=mock_post):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_session.return_value.post = mock_post
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
                mock_session.return_value.__aexit__ = AsyncMock()

                response = await adapter.chat("Hello")

        assert response == "test response"

    @pytest.mark.asyncio
    async def test_ollama_adapter_chat_with_context(self):
        """Test Ollama chat with conversation context."""
        from llm_adapter.ollama import OllamaAdapter

        adapter = OllamaAdapter()
        context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]

        mock_response = {"message": {"content": "How can I help?"}}
        mock_post = AsyncMock()
        mock_post.return_value = mock_response

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = mock_post
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()

            response = await adapter.chat("Follow-up question", context=context)

        assert response == "How can I help?"

    @pytest.mark.asyncio
    async def test_ollama_adapter_network_failure(self):
        """Test Ollama adapter handles network failure."""
        from llm_adapter.ollama import OllamaAdapter

        adapter = OllamaAdapter()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = AsyncMock(side_effect=ConnectionError("Connection refused"))

            with pytest.raises(ConnectionError):
                await adapter.chat("Hello")

    @pytest.mark.asyncio
    async def test_ollama_adapter_timeout(self):
        """Test Ollama adapter handles timeout."""
        from llm_adapter.ollama import OllamaAdapter

        adapter = OllamaAdapter()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = AsyncMock(side_effect=TimeoutError("Request timeout"))

            with pytest.raises(TimeoutError):
                await adapter.chat("Hello")

    @pytest.mark.asyncio
    async def test_ollama_adapter_invalid_response(self):
        """Test Ollama adapter handles invalid response format."""
        from llm_adapter.ollama import OllamaAdapter

        adapter = OllamaAdapter()

        mock_post = AsyncMock()
        mock_post.return_value = {"invalid": "format"}

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = mock_post
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()

            with pytest.raises(KeyError):
                await adapter.chat("Hello")


class TestDeepSeekAdapter:
    """Tests for DeepSeekAdapter."""

    @pytest.mark.asyncio
    async def test_deepseek_adapter_chat(self, mock_deepseek_response):
        """Test successful chat with DeepSeek adapter."""
        from llm_adapter.deepseek import DeepSeekAdapter

        adapter = DeepSeekAdapter()

        mock_post = AsyncMock()
        mock_post.return_value = mock_deepseek_response

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = mock_post
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()

            response = await adapter.chat("Hello")

        assert response == "test response"

    @pytest.mark.asyncio
    async def test_deepseek_adapter_chat_with_context(self):
        """Test DeepSeek chat with conversation context."""
        from llm_adapter.deepseek import DeepSeekAdapter

        adapter = DeepSeekAdapter()
        context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]

        mock_response = {"choices": [{"message": {"content": "How can I help?"}}]}
        mock_post = AsyncMock()
        mock_post.return_value = mock_response

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = mock_post
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()

            response = await adapter.chat("Follow-up question", context=context)

        assert response == "How can I help?"

    @pytest.mark.asyncio
    async def test_deepseek_adapter_api_error(self):
        """Test DeepSeek adapter handles API error."""
        from llm_adapter.deepseek import DeepSeekAdapter

        adapter = DeepSeekAdapter()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = AsyncMock(side_effect=Exception("API Error"))

            with pytest.raises(Exception):
                await adapter.chat("Hello")

    @pytest.mark.asyncio
    async def test_deepseek_adapter_rate_limit(self):
        """Test DeepSeek adapter handles rate limiting."""
        from llm_adapter.deepseek import DeepSeekAdapter

        adapter = DeepSeekAdapter()

        mock_post = AsyncMock()
        mock_post.return_value = {"error": {"message": "Rate limit exceeded"}}

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = mock_post
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.__aexit__ = AsyncMock()

            with pytest.raises(Exception):
                await adapter.chat("Hello")

    @pytest.mark.asyncio
    async def test_deepseek_adapter_invalid_api_key(self):
        """Test DeepSeek adapter handles invalid API key."""
        from llm_adapter.deepseek import DeepSeekAdapter

        adapter = DeepSeekAdapter()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.post = AsyncMock(side_effect=Exception("401 Unauthorized"))

            with pytest.raises(Exception):
                await adapter.chat("Hello")


class TestAdapterSwitching:
    """Tests for adapter switching mechanism."""

    def test_get_ollama_adapter(self):
        """Test getting Ollama adapter."""
        from llm_adapter import get_adapter

        with patch.dict("os.environ", {"LLM_PROVIDER": "ollama"}):
            adapter = get_adapter()
            assert adapter.__class__.__name__ == "OllamaAdapter"

    def test_get_deepseek_adapter(self):
        """Test getting DeepSeek adapter."""
        from llm_adapter import get_adapter

        with patch.dict("os.environ", {"LLM_PROVIDER": "deepseek"}):
            adapter = get_adapter()
            assert adapter.__class__.__name__ == "DeepSeekAdapter"

    def test_adapter_switching_env_change(self):
        """Test switching adapters by changing environment variable."""
        from llm_adapter import get_adapter

        with patch.dict("os.environ", {"LLM_PROVIDER": "ollama"}):
            adapter1 = get_adapter()
            assert adapter1.__class__.__name__ == "OllamaAdapter"

        with patch.dict("os.environ", {"LLM_PROVIDER": "deepseek"}, clear=False):
            adapter2 = get_adapter()
            assert adapter2.__class__.__name__ == "DeepSeekAdapter"

    def test_invalid_provider(self):
        """Test handling of invalid provider."""
        from llm_adapter import get_adapter

        with patch.dict("os.environ", {"LLM_PROVIDER": "invalid_provider"}):
            with pytest.raises(ValueError):
                get_adapter()
