import os
import tempfile
import pytest
import pytest_asyncio
from qq_bot.memory.store import MemoryStore


@pytest_asyncio.fixture
async def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = MemoryStore(path)
    yield s
    await s.close()
    os.unlink(path)


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_init_creates_tables(self, store):
        await store.init()
        tables = await store._fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [t[0] for t in tables]
        assert "sessions" in table_names
        assert "profiles" in table_names

    @pytest.mark.asyncio
    async def test_save_and_load_messages(self, store):
        await store.init()
        await store.save_message("group_123", "user", "你好", "111")
        await store.save_message("group_123", "assistant", "你好呀", "bot")
        msgs = await store.get_messages("group_123", limit=10)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_messages_limit(self, store):
        await store.init()
        for i in range(50):
            await store.save_message("group_123", "user", f"msg_{i}", "111")
        msgs = await store.get_messages("group_123", limit=10)
        assert len(msgs) == 10

    @pytest.mark.asyncio
    async def test_get_today_messages(self, store):
        await store.init()
        import time
        now = int(time.time())
        await store.save_message("group_123", "user", "today", "111", timestamp=now)
        await store.save_message("group_123", "user", "yesterday", "111", timestamp=now - 86400)
        msgs = await store.get_today_messages("group_123")
        assert len(msgs) == 1
        assert msgs[0]["content"] == "today"
