"""
检索器：用户提问 → 向量化 → FAISS 搜索 → 返回相关 chunks
"""

import os
from typing import Optional
from .embedder import Embedder
from .indexer import FAISSIndexer


class Retriever:
    """
    RAG 检索器
    流程：用户提问 → 向量化 → FAISS 搜索 → 返回 Top-K chunks
    """

    def __init__(
        self,
        index_path: str,
        embedder: Optional[Embedder] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ):
        """
        Args:
            index_path: FAISS 索引路径（不带扩展名）
            embedder: 向量化器，默认使用 bge-large-zh
            top_k: 返回最相似的 Top-K 条
            score_threshold: 相似度阈值，低于此值的丢弃
        """
        self.index_path = index_path
        self.embedder = embedder or Embedder()
        self.top_k = top_k
        self.score_threshold = score_threshold

        self._indexer: Optional[FAISSIndexer] = None

    def _ensure_loaded(self):
        """确保索引已加载"""
        if self._indexer is None:
            self._indexer = FAISSIndexer()
            self._indexer.load(self.index_path)

    def retrieve(self, query: str) -> list[str]:
        """
        检索相关 chunks

        Args:
            query: 用户提问

        Returns:
            list[str]: 相关的 chunk 内容列表（可能为空）
        """
        self._ensure_loaded()

        # 向量化查询
        query_embedding = self.embedder.encode_single(query)

        # 搜索
        results = self._indexer.search(query_embedding, k=self.top_k)

        # 按阈值过滤（L2距离越小越相似，所以用 <=）
        filtered = [
            (chunk, score) for chunk, score in results
            if score <= self.score_threshold
        ]

        # 只返回 chunk 内容
        return [chunk for chunk, _ in filtered]

    def retrieve_with_scores(self, query: str) -> list[tuple[str, float]]:
        """
        检索并返回 chunk + 分数

        Args:
            query: 用户提问

        Returns:
            list[tuple[str, float]]: [(chunk内容, 相似度分数), ...]
        """
        self._ensure_loaded()

        query_embedding = self.embedder.encode_single(query)
        results = self._indexer.search(query_embedding, k=self.top_k)

        return [
            (chunk, score) for chunk, score in results
            if score >= self.score_threshold
        ]


# === 便捷构建函数 ===

def build_index(
    documents: list[dict],
    output_path: str,
    embedder: Optional[Embedder] = None,
    index_type: str = "hnsw",
    chunk_max_chars: int = 500,
) -> FAISSIndexer:
    """
    从文档列表构建 FAISS 索引

    Args:
        documents: [{content: str, source: str}, ...]
        output_path: 索引保存路径（不带扩展名）
        embedder: 向量化器，默认 bge-large-zh
        index_type: flat 或 hnsw
        chunk_max_chars: chunk 最大字符数

    Returns:
        FAISSIndexer: 构建好的索引器
    """
    from .chunker import SessionChunker

    # 1. 分块
    chunker = SessionChunker(max_chars=chunk_max_chars)
    chunks = chunker.chunk_documents(documents)
    chunk_texts = [c.content for c in chunks]

    # 2. 向量化
    embedder = embedder or Embedder()
    embeddings = embedder.encode(chunk_texts)

    # 3. 构建索引
    indexer = FAISSIndexer(embedding_dim=embedder.embedding_dim, index_type=index_type)
    indexer.build(chunk_texts, embeddings)
    indexer.save(output_path)

    return indexer