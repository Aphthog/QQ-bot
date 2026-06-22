"""ChromaDB-backed semantic memory store."""
from __future__ import annotations

import logging
import time

import chromadb
from chromadb.config import Settings as ChromaSettings

from qq_bot.config import config

logger = logging.getLogger("qq_bot.memory.vector")


class VectorStore:
    def __init__(self, path: str = ""):
        self.path = path or config.CHROMA_PATH
        self._client: chromadb.Client | None = None
        self._collection: chromadb.Collection | None = None

    def _ensure_init(self) -> None:
        if self._client is not None:
            return
        import os
        os.makedirs(self.path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self.path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection("agent_memory")

    async def remember(self, chat_key: str, facts: list[str], metadata: dict | None = None) -> None:
        """Store facts into long-term memory."""
        if not facts:
            return
        self._ensure_init()
        ts = int(time.time())
        ids = [f"mem_{chat_key}_{ts}_{i}" for i in range(len(facts))]
        meta = metadata or {}
        metadatas = [{**meta, "chat_key": chat_key, "timestamp": ts} for _ in facts]
        try:
            self._collection.add(documents=facts, ids=ids, metadatas=metadatas)
        except Exception:
            logger.error("ChromaDB add failed", exc_info=True)

    async def recall(self, query: str, chat_key: str = "", k: int = 5) -> list[str]:
        """Retrieve relevant memories by semantic similarity."""
        self._ensure_init()
        where = {"chat_key": chat_key} if chat_key else None
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
                where=where,
            )
            docs = results.get("documents", [[]])[0]
            return [d for d in docs if d]
        except Exception:
            logger.error("ChromaDB query failed", exc_info=True)
            return []

    async def delete(self, memory_id: str) -> None:
        self._ensure_init()
        try:
            self._collection.delete(ids=[memory_id])
        except Exception:
            logger.error(f"ChromaDB delete failed for {memory_id}", exc_info=True)
