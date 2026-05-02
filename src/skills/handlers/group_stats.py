"""
Group Stats Skill - 群聊发言统计
"""

from collections import Counter


class GroupStatsSkill:
    """统计群聊发言数据"""

    async def execute(self, params: dict) -> str:
        """
        执行群聊统计
        params: {"group_id": "123456", "bot_self_id": "999999"}
        """
        group_id = params.get("group_id", "")
        bot_self_id = params.get("bot_self_id", "")

        # 从聊天历史加载
        from plugins.chat import _load_history
        history = _load_history(f"group_{group_id}")

        if not history:
            return "群聊记录为空，还没人说话呢~"

        # 统计发言次数（排除机器人）
        counts = Counter(
            m["qq"] for m in history
            if m.get("qq") and m["qq"] != bot_self_id
        )

        if not counts:
            return "群聊记录为空"

        # 取 Top 5
        top5 = counts.most_common(5)

        # 格式化输出
        lines = ["🏆 群聊发言排行榜 Top5："]
        for i, (qq, count) in enumerate(top5, 1):
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
            lines.append(f"{medal} <at qq='{qq}'/> 今日发送 {count} 条消息")

        return "\n".join(lines)