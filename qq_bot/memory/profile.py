"""Profile Manager: extracts and maintains per-user traits from conversations."""
from __future__ import annotations

import json
import logging
from typing import Any

from qq_bot.llm.base import build_messages

logger = logging.getLogger("qq_bot.memory.profile")

PROFILE_EXTRACT_PROMPT = """从对话中提取用户的特征标签。输出 JSON：{"traits": {"key": "value", ...}}

可提取的信息类型：
- interests: 兴趣爱好
- location: 所在地
- occupation: 职业/专业
- preferences: 偏好
- pets: 宠物
- other: 其他值得记录的信息

只输出 JSON。如果没有新发现，输出空的 traits。"""


class ProfileManager:
    def __init__(self, store, llm: Any):
        self.store = store
        self.llm = llm
        self._update_counters: dict[str, int] = {}

    async def update_profile(
        self, user_id: str, nickname: str, messages: list[dict], force: bool = False,
    ) -> None:
        """Extract traits from messages and merge into user profile."""
        self._update_counters[user_id] = self._update_counters.get(user_id, 0) + 1

        if not force and self._update_counters[user_id] < 50:
            return

        self._update_counters[user_id] = 0

        dialogs_text = "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in messages[-20:]
        )

        msgs = build_messages(
            system_prompt=PROFILE_EXTRACT_PROMPT,
            user_text=f"用户 {nickname or user_id} 的对话:\n{dialogs_text}",
        )

        try:
            raw = await self.llm.chat(msgs, max_tokens=200, temperature=0.1)
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) >= 3 else raw
            data = json.loads(raw)
            traits = data.get("traits", {})
            if traits:
                await self.store.upsert_profile(user_id, nickname, traits)
                logger.debug(f"Profile updated for {user_id}: {traits}")
        except Exception:
            logger.error(f"Profile extraction failed for {user_id}", exc_info=True)

    async def get_profile(self, user_id: str) -> dict | None:
        return await self.store.get_profile(user_id)
