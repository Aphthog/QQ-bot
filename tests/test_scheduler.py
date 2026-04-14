"""
Test suite for scheduler plugin and content sources.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
sys.path.insert(0, "/c/Users/Camille/Desktop/qq-bot")


class TestSchedulerPlugin:
    """Tests for scheduler plugin functionality."""

    @pytest.mark.asyncio
    async def test_news_fetch(self):
        """Test news content source fetch."""
        from plugins.scheduler.sources.news import NewsSource

        source = NewsSource()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "articles": [
                {"title": "Breaking News", "description": "Test article"}
            ]
        })

        with patch("aiohttp.ClientSession.get", return_value=mock_response):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_session.return_value.get = AsyncMock(return_value=mock_response)
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
                mock_session.return_value.__aexit__ = AsyncMock()

                result = await source.fetch()

        assert "Breaking News" in result or "news" in result.lower()

    @pytest.mark.asyncio
    async def test_news_fetch_network_failure(self):
        """Test news source handles network failure."""
        from plugins.scheduler.sources.news import NewsSource

        source = NewsSource()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.get = AsyncMock(side_effect=ConnectionError("Network error"))

            with pytest.raises(ConnectionError):
                await source.fetch()

    @pytest.mark.asyncio
    async def test_weather_fetch(self):
        """Test weather content source fetch."""
        from plugins.scheduler.sources.weather import WeatherSource

        source = WeatherSource()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "weather": [{"description": "sunny", "temp": 25}]
        })

        with patch("aiohttp.ClientSession.get", return_value=mock_response):
            with patch("aiohttp.ClientSession") as mock_session:
                mock_session.return_value.get = AsyncMock(return_value=mock_response)
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
                mock_session.return_value.__aexit__ = AsyncMock()

                result = await source.fetch()

        assert "weather" in result.lower() or "25" in result or "sunny" in result.lower()

    @pytest.mark.asyncio
    async def test_weather_fetch_api_error(self):
        """Test weather source handles API error."""
        from plugins.scheduler.sources.weather import WeatherSource

        source = WeatherSource()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.get = AsyncMock(side_effect=Exception("API Error"))

            with pytest.raises(Exception):
                await source.fetch()

    @pytest.mark.asyncio
    async def test_custom_source_fetch(self):
        """Test custom content source fetch."""
        from plugins.scheduler.sources.custom import CustomSource

        source = CustomSource()

        result = await source.fetch()

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_schedule_broadcast(self):
        """Test scheduled broadcast execution."""
        from plugins.scheduler import execute_scheduled_broadcast

        mock_bot = MagicMock()
        mock_bot.send_group_message = AsyncMock()

        groups = [
            {"group_id": "123456", "name": "Group 1"},
            {"group_id": "789012", "name": "Group 2"}
        ]

        news_source = MagicMock()
        news_source.fetch = AsyncMock(return_value="Today's news: Test news content")

        with patch("plugins.scheduler.list_groups", return_value=groups):
            with patch("plugins.scheduler.get_source", return_value=news_source):
                await execute_scheduled_broadcast(mock_bot, "news")

        assert mock_bot.send_group_message.call_count == 2
        news_source.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_broadcast_empty_groups(self):
        """Test scheduled broadcast with no groups configured."""
        from plugins.scheduler import execute_scheduled_broadcast

        mock_bot = MagicMock()
        mock_bot.send_group_message = AsyncMock()

        with patch("plugins.scheduler.list_groups", return_value=[]):
            await execute_scheduled_broadcast(mock_bot, "news")

        mock_bot.send_group_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_source_timeout(self):
        """Test source fetch handles timeout."""
        from plugins.scheduler.sources.news import NewsSource

        source = NewsSource()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.get = AsyncMock(side_effect=TimeoutError("Request timeout"))

            with pytest.raises(TimeoutError):
                await source.fetch()

    def test_base_source_interface(self):
        """Test BaseSource abstract interface."""
        from plugins.scheduler.sources.base import BaseSource

        with pytest.raises(TypeError):
            source = BaseSource()

    def test_source_name_property(self):
        """Test that sources have correct name property."""
        from plugins.scheduler.sources.news import NewsSource
        from plugins.scheduler.sources.weather import WeatherSource

        news_source = NewsSource()
        weather_source = WeatherSource()

        assert news_source.name == "news"
        assert weather_source.name == "weather"


class TestSchedulerIntegration:
    """Integration tests for scheduler with content sources."""

    @pytest.mark.asyncio
    async def test_all_sources_registered(self):
        """Test all content sources are properly registered."""
        from plugins.scheduler import get_source

        news = get_source("news")
        weather = get_source("weather")
        custom = get_source("custom")

        assert news is not None
        assert weather is not None
        assert custom is not None

    @pytest.mark.asyncio
    async def test_unknown_source_raises_error(self):
        """Test that unknown source raises error."""
        from plugins.scheduler import get_source

        with pytest.raises(ValueError):
            get_source("unknown_source")

    @pytest.mark.asyncio
    async def test_morning_broadcast_schedule(self):
        """Test morning broadcast schedule execution."""
        from plugins.scheduler import execute_scheduled_broadcast

        mock_bot = MagicMock()
        mock_bot.send_group_message = AsyncMock()

        groups = [{"group_id": "123456", "name": "Morning Group"}]

        weather_source = MagicMock()
        weather_source.fetch = AsyncMock(return_value="Good morning! Weather today: Sunny, 22C")

        with patch("plugins.scheduler.list_groups", return_value=groups):
            with patch("plugins.scheduler.get_source", return_value=weather_source):
                await execute_scheduled_broadcast(mock_bot, "weather")

        mock_bot.send_group_message.assert_called_once_with(
            "123456",
            "Good morning! Weather today: Sunny, 22C"
        )

    @pytest.mark.asyncio
    async def test_multiple_content_types_in_broadcast(self):
        """Test broadcast with multiple content types."""
        from plugins.scheduler import execute_scheduled_broadcast

        mock_bot = MagicMock()
        mock_bot.send_group_message = AsyncMock()

        groups = [{"group_id": "123456", "name": "Group"}]

        news_source = MagicMock()
        news_source.fetch = AsyncMock(return_value="News: Test news")

        with patch("plugins.scheduler.list_groups", return_value=groups):
            with patch("plugins.scheduler.get_source", return_value=news_source):
                await execute_scheduled_broadcast(mock_bot, "news,weather")

        assert mock_bot.send_group_message.call_count >= 1
