"""
Group Stats Skill - 群聊发言统计
"""

from collections import Counter
from datetime import date, datetime, time

from qq_bot.services.chat_history import history_store
from .base import BaseSkill


class GroupStatsSkill(BaseSkill):
    name = "top"
    description = "群聊发言排行榜"

    async def execute(self, params: dict, context: dict | None = None) -> str:
        group_id = params.get("group_id", "")
        bot_self_id = params.get("bot_self_id", "")
        history = history_store.load(f"group_{group_id}")

        if not history:
            return "群聊记录为空，还没人说话呢~"

        today_start = int(datetime.combine(date.today(), time.min).timestamp())
        today_msgs = [m for m in history if m.get("time", 0) >= today_start and m.get("qq") and m["qq"] != bot_self_id]
        if not today_msgs:
            return "今天还没有人说话呢~"

        counts = Counter(m["qq"] for m in today_msgs)
        top5 = counts.most_common(5)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = ["📊 今日发言排行榜 Top5："]
        for i, (qq, count) in enumerate(top5, 1):
            name = await self._get_group_card(params, qq)
            lines.append(f"{medals[i-1]} {name} 发言 {count} 条")
        return "\n".join(lines)
