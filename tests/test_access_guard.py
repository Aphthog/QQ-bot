import pytest
from qq_bot.access.guard import AccessGuard
from qq_bot.config import config


class DummyStore:
    async def get_profile(self, user_id):
        return None


class TestAccessGuard:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_normal_use(self):
        guard = AccessGuard(DummyStore())
        ok, msg = await guard.check_rate("user_1")
        assert ok is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_spam(self):
        guard = AccessGuard(DummyStore())
        for _ in range(10):
            await guard.check_rate("user_2")
        ok, msg = await guard.check_rate("user_2")
        assert ok is False
        assert "太快" in msg

    def test_superuser_recognized(self, monkeypatch):
        monkeypatch.setenv("SUPERUSERS", '["admin_qq"]')
        # Clear cached_property cache so the new env var is picked up
        config.__dict__.pop("SUPERUSERS", None)
        guard = AccessGuard(DummyStore())
        assert guard.is_superuser("admin_qq") is True
        assert guard.is_superuser("random_user") is False
