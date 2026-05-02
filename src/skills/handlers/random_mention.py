"""
Random Mention Skill - 随机艾特群友
"""

import random
import time


class RandomMentionSkill:
    """从群聊活跃用户中随机艾特一人"""

    async def execute(self, params: dict) -> str:
        """
        执行随机艾特
        params: {"group_id": "123456", "bot_self_id": "999999"}
        """
        group_id = params.get("group_id", "")
        bot_self_id = params.get("bot_self_id", "")

        # 从聊天历史加载
        from plugins.chat import _load_history
        history = _load_history(f"group_{group_id}")

        if not history:
            return "群聊记录为空，还没人说话呢~"

        # 逐步扩大时间窗口，直到可艾特人数 >= 7
        time_window = 30 * 60  # 初始 30 分钟
        min_candidates = 7

        while time_window <= 24 * 60 * 60:  # 最多看 24 小时
            cutoff_time = int(time.time()) - time_window
            active_users = list(set(
                m["qq"] for m in history
                if m.get("qq")
                and m["qq"] != bot_self_id
                and m.get("time", 0) >= cutoff_time
            ))
            if len(active_users) >= min_candidates:
                break
            time_window *= 2  # 时间窗口翻倍

        if not active_users:
            return "最近没有活跃用户，无法艾特"

        chosen = random.choice(active_users)
        return f"<at qq='{chosen}'/>"