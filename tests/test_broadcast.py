"""
Test suite for broadcast plugin.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import sys
sys.path.insert(0, "/c/Users/Camille/Desktop/qq-bot")


class TestBroadcastPlugin:
    """Tests for broadcast plugin functionality."""

    def test_add_group(self):
        """Test adding a group to broadcast list."""
        from plugins.broadcast import add_group

        groups_file_path = "/c/Users/Camille/Desktop/qq-bot/data/broadcast_groups.json"
        existing_groups = [{"group_id": "123456", "name": "Test Group"}]

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                result = add_group("789012", "New Group")

        assert result is True
        mock_file().write.assert_called()

    def test_add_duplicate_group(self):
        """Test adding a duplicate group returns False."""
        from plugins.broadcast import add_group

        existing_groups = [{"group_id": "123456", "name": "Test Group"}]

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                result = add_group("123456", "Duplicate Group")

        assert result is False

    def test_remove_group(self):
        """Test removing a group from broadcast list."""
        from plugins.broadcast import remove_group

        groups_file_path = "/c/Users/Camille/Desktop/qq-bot/data/broadcast_groups.json"
        existing_groups = [
            {"group_id": "123456", "name": "Test Group"},
            {"group_id": "789012", "name": "Another Group"}
        ]

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                result = remove_group("123456")

        assert result is True
        mock_file().write.assert_called()

    def test_remove_nonexistent_group(self):
        """Test removing a group that doesn't exist returns False."""
        from plugins.broadcast import remove_group

        existing_groups = [{"group_id": "123456", "name": "Test Group"}]

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                result = remove_group("nonexistent")

        assert result is False

    def test_list_groups(self):
        """Test listing all broadcast groups."""
        from plugins.broadcast import list_groups

        groups_file_path = "/c/Users/Camille/Desktop/qq-bot/data/broadcast_groups.json"
        existing_groups = [
            {"group_id": "123456", "name": "Test Group"},
            {"group_id": "789012", "name": "Another Group"}
        ]

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                result = list_groups()

        assert len(result) == 2
        assert result[0]["group_id"] == "123456"
        assert result[1]["group_id"] == "789012"

    def test_list_groups_empty(self):
        """Test listing groups when list is empty."""
        from plugins.broadcast import list_groups

        mock_file = mock_open(read_data=json.dumps([]))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=[]):
                result = list_groups()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_manual_broadcast(self):
        """Test manual broadcast to all groups."""
        from plugins.broadcast import manual_broadcast

        groups = [
            {"group_id": "123456", "name": "Group 1"},
            {"group_id": "789012", "name": "Group 2"}
        ]

        mock_bot = MagicMock()
        mock_bot.send_group_message = AsyncMock()

        with patch("plugins.broadcast.list_groups", return_value=groups):
            await manual_broadcast(mock_bot, "Test broadcast message")

        assert mock_bot.send_group_message.call_count == 2

    @pytest.mark.asyncio
    async def test_manual_broadcast_to_specific_group(self):
        """Test broadcast to a specific group."""
        from plugins.broadcast import broadcast_to_group

        mock_bot = MagicMock()
        mock_bot.send_group_message = AsyncMock()

        await broadcast_to_group(mock_bot, "123456", "Targeted message")

        mock_bot.send_group_message.assert_called_once_with("123456", "Targeted message")

    @pytest.mark.asyncio
    async def test_broadcast_file_not_found(self):
        """Test broadcast handles missing groups file."""
        from plugins.broadcast import list_groups

        with patch("builtins.open", side_effect=FileNotFoundError()):
            with patch("json.load", return_value=[]):
                result = list_groups()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_broadcast_invalid_json(self):
        """Test broadcast handles corrupt JSON file."""
        from plugins.broadcast import list_groups

        with patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
            result = list_groups()

        assert len(result) == 0

    def test_add_group_updates_file(self):
        """Test that add_group properly writes to file."""
        from plugins.broadcast import add_group

        existing_groups = []
        new_groups = [{"group_id": "123456", "name": "New Group"}]

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                with patch("json.dump") as mock_dump:
                    add_group("123456", "New Group")
                    mock_dump.assert_called()

    def test_remove_group_updates_file(self):
        """Test that remove_group properly writes to file."""
        from plugins.broadcast import remove_group

        existing_groups = [{"group_id": "123456", "name": "Test Group"}]
        updated_groups = []

        mock_file = mock_open(read_data=json.dumps(existing_groups))

        with patch("builtins.open", mock_file):
            with patch("json.load", return_value=existing_groups):
                with patch("json.dump") as mock_dump:
                    remove_group("123456")
                    mock_dump.assert_called()
