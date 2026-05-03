"""
聊天历史存储：JSON 文件存储，支持按群/私聊分文件。
供插件层和技能层共同使用，消除循环引用。
"""

import json
import os
import time

from qq_bot.config import settings
from qq_bot.security.rules import BLOCKED_KEYWORDS


class ChatHistoryStore:
    """聊天历史存储，每个 chat_key 独立文件"""

    def __init__(
        self,
        chat_dir: str = "",
        group_max_turns: int = 0,
    ):
        self.chat_dir = chat_dir or settings.HISTORY_DIR
        self.group_max_turns = group_max_turns or settings.GROUP_HISTORY_MAX_TURNS
        os.makedirs(self.chat_dir, exist_ok=True)

    def load(self, chat_key: str) -> list[dict]:
        """加载聊天历史"""
        path = os.path.join(self.chat_dir, f"{chat_key}.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        return data[-self.group_max_turns:]

    def save(self, chat_key: str, role: str, content: str, qq: str):
        """保存一条消息。含敏感词的跳过不存，防止被二次利用。"""
        lower = content.lower()
        if any(kw in lower for kw in BLOCKED_KEYWORDS):
            return
        path = os.path.join(self.chat_dir, f"{chat_key}.json")
        messages = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                messages = []
        messages.append({"role": role, "content": content, "qq": qq, "time": int(time.time())})
        messages = messages[-self.group_max_turns:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    @staticmethod
    def format_as_context(messages: list[dict], label: str) -> list[dict]:
        """格式化为龙猫兼容的 system context"""
        if not messages:
            return []
        lines = [label]
        for m in messages:
            role = "Bot" if m["role"] == "assistant" else f"User_{m['qq']}"
            lines.append(f"{role}: {m['content']}")
        return [{"role": "system", "content": [{"type": "text", "text": "\n".join(lines)}]}]

    def build_context(
        self,
        chat_key: str,
        user_id: str,
        target_qq: str | None = None,
        recent_limit: int = 15,
    ) -> list[dict]:
        """构建上下文。所有历史合并为一条 system 消息（LongCat 兼容格式）。"""
        history = self.load(chat_key)

        recent = history[-recent_limit:]
        # 排除刚刚由 group_watcher 存进来的当前消息
        if recent and recent[-1].get("qq") == user_id:
            recent = recent[:-1]

        if not recent:
            return []

        lines = ["【最近群聊消息】"]
        for m in recent:
            label = f"User_{m['qq']}" if m["role"] == "user" else "Bot"
            lines.append(f"{label}: {m['content']}")

        if target_qq:
            extra = [m for m in history if m.get("qq") == target_qq][-10:]
            if extra:
                lines.append("")
                lines.append(f"以下是 {target_qq} 的更多发言：")
                for m in extra:
                    label = f"User_{m['qq']}" if m["role"] == "user" else "Bot"
                    lines.append(f"{label}: {m['content']}")

        return [{"role": "system", "content": [{"type": "text", "text": "\n".join(lines)}]}]


# 全局单例
history_store = ChatHistoryStore()
