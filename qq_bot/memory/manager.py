"""MemoryManager: unified interface over Store + VectorStore + ProfileManager."""
from __future__ import annotations

import logging
from typing import Any

from qq_bot.memory.store import MemoryStore
from qq_bot.memory.vector import VectorStore
from qq_bot.memory.profile import ProfileManager

logger = logging.getLogger("qq_bot.memory")


class MemoryManager:
    def __init__(self, store: MemoryStore, vector: VectorStore, profile_mgr: ProfileManager):
        self.store = store
        self.vector = vector
        self.profiles = profile_mgr

    async def init(self) -> None:
        await self.store.init()

    # ── Working Memory ────────────────────────────

    async def save(self, chat_key: str, role: str, content: str, user_id: str = "") -> None:
        await self.store.save_message(chat_key, role, content, user_id)

    async def get_context(self, chat_key: str, limit: int = 30) -> list[dict]:
        return await self.store.get_messages(chat_key, limit)

    # ── Semantic Memory ───────────────────────────

    async def remember(self, chat_key: str, facts: list[str]) -> None:
        await self.vector.remember(chat_key, facts)

    async def recall(self, query: str, chat_key: str = "") -> str:
        results = await self.vector.recall(query, chat_key, k=5)
        return "\n".join(f"- {r}" for r in results) if results else ""

    # ── Profiles ──────────────────────────────────

    async def update_profile(self, user_id: str, nickname: str = "", messages: list[dict] | None = None) -> None:
        await self.profiles.update_profile(user_id, nickname, messages or [])

    async def get_profile(self, user_id: str) -> dict | None:
        return await self.profiles.get_profile(user_id)

    # ── Fact Extraction ───────────────────────────

    async def extract_and_remember(self, chat_key: str, messages: list[dict]) -> None:
        """After a conversation turn, extract facts and store to vector memory."""
        if len(messages) < 2:
            return
        dialogs = "\n".join(
            f"{m['role']}: {m['content'][:300]}" for m in messages[-6:]
        )
        from qq_bot.llm.base import build_messages
        msgs = build_messages(
            system_prompt="从对话中提取值得记住的事实（人物信息、约定、偏好等）。每行一个事实。没有就输出 NONE。",
            user_text=dialogs,
        )
        try:
            raw = await self.profiles.llm.chat(msgs, max_tokens=200, temperature=0.1)
            if raw.strip().upper() == "NONE":
                return
            facts = [line.strip("- ").strip() for line in raw.split("\n") if line.strip() and "NONE" not in line]
            if facts:
                await self.remember(chat_key, facts)
        except Exception:
            logger.error("Fact extraction failed", exc_info=True)
