"""
Memory Skill - 存入知识库
"""

import re
import asyncio
import os


class MemorySkill:
    """将网页内容存入知识库"""

    async def execute(self, params: dict) -> str:
        """
        执行存入知识库
        params: {"url": "https://..."}
        """
        url = params.get("url", "")
        if not url:
            return "请提供要存入的网址，格式：/memory <网址>"

        # 爬取内容
        from src.tools.crawler import crawl_url_async
        from src.llm_adapter.rag.chunker import SessionChunker
        from src.llm_adapter.rag.embedder import Embedder
        from src.llm_adapter.rag.indexer import FAISSIndexer

        content_text = await crawl_url_async(url)
        if not content_text:
            return "网页获取失败，请检查URL是否正确"

        if len(content_text) < 50:
            return "网页内容太少，无法存入知识库"

        # 分块
        chunker = SessionChunker(max_chars=500)
        chunks = chunker.chunk_documents([
            {"content": content_text, "source": url}
        ])

        # 过滤太短的 chunks
        valid_chunks = [c for c in chunks if len(c.content.strip()) >= 30]
        print(f"[memory] 分块: {len(chunks)}, 过滤后: {len(valid_chunks)}")

        if not valid_chunks:
            return "内容太少，无法存入知识库"

        # 向量化
        embedder = Embedder()
        chunk_texts = [c.content for c in valid_chunks]
        embeddings = await asyncio.to_thread(embedder.encode, chunk_texts)

        # 索引
        index_path = "src/data/knowledge_index"
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