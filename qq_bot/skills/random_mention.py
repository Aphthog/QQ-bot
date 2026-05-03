"""
Random Mention Skill - 随机艾特群友
"""

import random
import time

from qq_bot.services.chat_history import history_store
from .base import BaseSkill


class RandomMentionSkill(BaseSkill):
    name = "random"
    description = "随机艾特群友"

    async def execute(self, params: dict, context: dict | None = None) -> str:
        group_id = params.get("group_id", "")
        bot_self_id = params.get("bot_self_id", "")
        history = history_store.load(f"group_{group_id}")

        if not history:
            return "群聊记录为空，还没人说话呢~"

        time_window = 30 * 60
        min_candidates = 7
        active_users = []

        while time_window <= 24 * 60 * 60:
            cutoff = int(time.time()) - time_window
            active_users = list(set(
                m["qq"] for m in history
                if m.get("qq") and m["qq"] != bot_self_id and m.get("time", 0) >= cutoff
            ))
            if len(active_users) >= min_candidates:
                break
            time_window *= 2

        if not active_users:
            return "最近没有活跃用户，无法艾特"

        chosen = random.choice(active_users)
        name = await self._get_group_card(params, chosen)
        return f"@{name}"
