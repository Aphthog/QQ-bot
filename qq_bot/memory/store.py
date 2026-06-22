"""SQLite-backed message and profile storage."""
from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite


class MemoryStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        import os
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_key TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT '',
                timestamp INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_key_ts ON sessions(chat_key, timestamp DESC);

            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL DEFAULT '',
                traits TEXT NOT NULL DEFAULT '{}',
                first_seen INTEGER NOT NULL DEFAULT 0,
                last_seen INTEGER NOT NULL DEFAULT 0,
                interaction_count INTEGER NOT NULL DEFAULT 0
            );
        """)
        await self._db.commit()

    async def _fetch_all(self, sql: str, params: tuple = ()) -> list[Any]:
        cursor = await self._db.execute(sql, params)
        return await cursor.fetchall()

    async def save_message(
        self, chat_key: str, role: str, content: str, user_id: str,
        timestamp: int | None = None,
    ) -> None:
        ts = timestamp or int(time.time())
        await self._db.execute(
            "INSERT INTO sessions (chat_key, role, content, user_id, timestamp) VALUES (?,?,?,?,?)",
            (chat_key, role, content, user_id, ts),
        )
        await self._db.commit()

    async def get_messages(self, chat_key: str, limit: int = 30) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT role, content, user_id, timestamp FROM sessions "
            "WHERE chat_key = ? ORDER BY timestamp DESC, id DESC LIMIT ?",
            (chat_key, limit),
        )
        rows = await cursor.fetchall()
        msgs = [dict(r) for r in reversed(rows)]
        return msgs

    async def get_today_messages(self, chat_key: str) -> list[dict]:
        now = int(time.time())
        start_of_day = now - (now % 86400)
        cursor = await self._db.execute(
            "SELECT role, content, user_id, timestamp FROM sessions "
            "WHERE chat_key = ? AND timestamp >= ? ORDER BY timestamp ASC",
            (chat_key, start_of_day),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def upsert_profile(self, user_id: str, nickname: str = "", traits: dict | None = None) -> None:
        now = int(time.time())
        existing = await self._db.execute(
            "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
        )
        row = await existing.fetchone()
        if row:
            current_traits = json.loads(row["traits"])
            if traits:
                current_traits.update(traits)
            await self._db.execute(
                "UPDATE profiles SET nickname=?, traits=?, last_seen=?, interaction_count=? WHERE user_id=?",
                (nickname or row["nickname"], json.dumps(current_traits, ensure_ascii=False),
                 now, row["interaction_count"] + 1, user_id),
            )
        else:
            await self._db.execute(
                "INSERT INTO profiles (user_id, nickname, traits, first_seen, last_seen, interaction_count) "
                "VALUES (?,?,?,?,?,1)",
                (user_id, nickname, json.dumps(traits or {}, ensure_ascii=False), now, now),
            )
        await self._db.commit()

    async def get_profile(self, user_id: str) -> dict | None:
        cursor = await self._db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def close(self) -> None:
        if self._db:
            await self._db.close()
