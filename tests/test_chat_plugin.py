"""
Test suite for chat plugin.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
sys.path.insert(0, "/c/Users/Camille/Desktop/qq-bot")


class TestChatPlugin:
    """Tests for chat plugin functionality."""

    @pytest.mark.asyncio
    async def test_mentioned_reply(self):
        """Test bot replies when mentioned."""
        from plugins.chat import handle_mention

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="What is the weather?")
        mock_event.is_mentioned = True

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="The weather is sunny.")

        with patch("plugins.chat.get_llm_adapter", return_value=mock_llm):
            await handle_mention(mock_bot, mock_event)

        mock_llm.chat.assert_called_once()
        mock_bot.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_private_chat(self):
        """Test bot handles private chat messages."""
        from plugins.chat import handle_private_message

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="Hello bot")
        mock_event.is_private = True

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Hello! How can I help?")

        with patch("plugins.chat.get_llm_adapter", return_value=mock_llm):
            await handle_private_message(mock_bot, mock_event)

        mock_llm.chat.assert_called_once()
        mock_bot.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_mentioned_reply_with_context(self):
        """Test bot maintains conversation context."""
        from plugins.chat import handle_mention

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="Continue from before")
        mock_event.is_mentioned = True
        mock_event.get_context = MagicMock(return_value=[
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ])

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Continuing the conversation...")

        with patch("plugins.chat.get_llm_adapter", return_value=mock_llm):
            await handle_mention(mock_bot, mock_event)

        mock_llm.chat.assert_called_once()
        call_args = mock_llm.chat.call_args
        assert call_args[1]["context"] is not None

    @pytest.mark.asyncio
    async def test_ollama_fallback_on_deepseek_failure(self):
        """Test fallback to Ollama when DeepSeek fails."""
        from plugins.chat import handle_mention

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="Hello")
        mock_event.is_mentioned = True

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        deepseek_llm = AsyncMock()
        deepseek_llm.chat = AsyncMock(side_effect=ConnectionError("DeepSeek unavailable"))

        ollama_llm = AsyncMock()
        ollama_llm.chat = AsyncMock(return_value="Response from Ollama fallback")

        with patch("plugins.chat.get_llm_adapter", return_value=deepseek_llm):
            with patch("plugins.chat.get_fallback_adapter", return_value=ollama_llm):
                await handle_mention(mock_bot, mock_event)

        ollama_llm.chat.assert_called_once()
        mock_bot.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_image(self):
        """Test chat plugin handles image input."""
        from plugins.chat import handle_mention_with_image

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="What is in this image?")
        mock_event.get_image = AsyncMock(return_value=b"fake_image_bytes")
        mock_event.is_mentioned = True

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="The image shows a cat.")

        with patch("plugins.chat.get_llm_adapter", return_value=mock_llm):
            await handle_mention_with_image(mock_bot, mock_event)

        mock_llm.chat.assert_called_once()
        call_args = mock_llm.chat.call_args
        assert call_args[1]["image"] == b"fake_image_bytes"

    @pytest.mark.asyncio
    async def test_mentioned_reply_llm_unavailable(self):
        """Test bot handles LLM being unavailable."""
        from plugins.chat import handle_mention

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="Hello")
        mock_event.is_mentioned = True

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        with patch("plugins.chat.get_llm_adapter", side_effect=Exception("LLM not configured")):
            await handle_mention(mock_bot, mock_event)

        mock_bot.send.assert_called_once()
        call_args = mock_bot.send.call_args
        assert "error" in str(call_args).lower() or "unavailable" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_empty_message(self):
        """Test bot handles empty message gracefully."""
        from plugins.chat import handle_mention

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="")
        mock_event.is_mentioned = True

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Please say something.")

        with patch("plugins.chat.get_llm_adapter", return_value=mock_llm):
            await handle_mention(mock_bot, mock_event)

        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_history_saved(self):
        """Test that chat history is saved after conversation."""
        from plugins.chat import handle_mention

        mock_event = MagicMock()
        mock_event.get_message = AsyncMock(return_value="Hello")
        mock_event.is_mentioned = True
        mock_event.user_id = "12345"

        mock_bot = MagicMock()
        mock_bot.send = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Hi there!")

        mock_history = MagicMock()
        mock_history.save = AsyncMock()

        with patch("plugins.chat.get_llm_adapter", return_value=mock_llm):
            with patch("plugins.chat.get_history_manager", return_value=mock_history):
                await handle_mention(mock_bot, mock_event)

        mock_history.save.assert_called_once()
