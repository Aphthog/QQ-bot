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
        recent_limit: int = 5,
    ) -> list[dict]:
        """构建带标签的上下文。用实际 user/assistant 角色而非全塞 system 消息，让 LLM 真正理解对话流。"""
        history = self.load(chat_key)
        ctx: list[dict] = []

        recent = history[-recent_limit:]
        if recent:
            ctx.append({"role": "system", "content": "【最近群聊风向】（以下是群内近期消息）"})
            for m in recent:
                role = m["role"]
                content = m["content"]
                if role == "user" and m.get("qq"):
                    content = f"[{m['qq']}] {content}"
                ctx.append({"role": role, "content": content})

        five_min_ago = int(time.time()) - 300
        personal = [m for m in history if m.get("qq") == user_id and m.get("time", 0) >= five_min_ago][-10:]
        if personal:
            ctx.append({"role": "system", "content": "【你与该用户的往来记录】（以下是该用户近期对你说的话）"})
            for m in personal:
                content = m["content"]
                if m.get("qq"):
                    content = f"[{m['qq']}] {content}"
                ctx.append({"role": "user", "content": content})

        if target_qq:
            msgs = [m for m in history if m.get("qq") == target_qq][-10:]
            if msgs:
                ctx.append({"role": "system", "content": f"【{target_qq}的发言】（以下是该用户的近期消息）"})
                for m in msgs:
                    role = m["role"]
                    content = m["content"]
                    if role == "user" and m.get("qq"):
                        content = f"[{m['qq']}] {content}"
                    ctx.append({"role": role, "content": content})

        return ctx


# 全局单例
history_store = ChatHistoryStore()
