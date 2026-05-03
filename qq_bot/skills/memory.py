"""
Memory Skill - 存入知识库
"""

import asyncio
import os

from qq_bot.config import settings
from qq_bot.rag.chunker import SessionChunker
from qq_bot.rag.embedder import Embedder
from qq_bot.rag.indexer import FAISSIndexer
from qq_bot.services.crawler import crawl_url_async
from .base import BaseSkill


class MemorySkill(BaseSkill):
    name = "memory"
    description = "将网页内容存入知识库"

    async def execute(self, params: dict, context: dict | None = None) -> str:
        url = params.get("url", "")
        if not url:
            return "请提供要存入的网址，格式：/memory <网址>"

        content_text = await crawl_url_async(url)
        if not content_text:
            return "网页获取失败，请检查URL是否正确"

        if len(content_text) < 50:
            return "网页内容太少，无法存入知识库"

        chunker = SessionChunker(max_chars=500)
        chunks = chunker.chunk_documents([{"content": content_text, "source": url}])
        valid_chunks = [c for c in chunks if len(c.content.strip()) >= 30]
        if not valid_chunks:
            return "内容太少，无法存入知识库"

        embedder = Embedder()
        chunk_texts = [c.content for c in valid_chunks]
        embeddings = await asyncio.to_thread(embedder.encode, chunk_texts)

        index_path = settings.KNOWLEDGE_INDEX_PATH
        embedding_dim = embedder.embedding_dim

        if os.path.exists(f"{index_path}.index"):
            indexer = FAISSIndexer(embedding_dim=embedding_dim)
            indexer.load(index_path)
        else:
            indexer = FAISSIndexer(embedding_dim=embedding_dim, index_type="hnsw")
            indexer.build([], embeddings[:0])

        indexer.add(chunk_texts, embeddings)
        os.makedirs(os.path.dirname(index_path) or ".", exist_ok=True)
        indexer.save(index_path)

        return f"已存入知识库（{len(valid_chunks)}个片段）"
