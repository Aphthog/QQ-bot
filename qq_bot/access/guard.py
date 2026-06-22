"""Access Guard: permission checks and rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from qq_bot.config import config


class AccessGuard:
    def __init__(self, store: Any):
        self.store = store
        self._rate_limits: dict[str, list[float]] = defaultdict(list)
        self._cooldowns: dict[str, float] = {}

    def is_superuser(self, user_id: str) -> bool:
        return user_id in config.SUPERUSERS

    async def is_banned(self, user_id: str) -> bool:
        row = await self.store.get_profile(user_id)
        if row and row.get("level") == "banned":
            return True
        return False

    async def check_rate(self, user_id: str, group_id: str = "") -> tuple[bool, str]:
        """Returns (allowed, reason)."""
        if self.is_superuser(user_id):
            return True, ""

        now = time.time()

        # Cooldown check
        if user_id in self._cooldowns and now - self._cooldowns[user_id] < 60:
            return False, "歇一歇，太快啦～（冷却中）"

        # User rate
        key_u = f"u:{user_id}"
        self._rate_limits[key_u] = [t for t in self._rate_limits[key_u] if now - t < 60]
        if len(self._rate_limits[key_u]) >= 10:
            self._cooldowns[user_id] = now
            return False, "太快啦，歇一下～"
        self._rate_limits[key_u].append(now)

        # Group rate
        if group_id:
            key_g = f"g:{group_id}"
            self._rate_limits[key_g] = [t for t in self._rate_limits[key_g] if now - t < 60]
            if len(self._rate_limits[key_g]) >= 30:
                return False, "群聊太热闹了，慢一点～"

        return True, ""
