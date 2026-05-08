from typing import Optional

from qq_bot.config import settings
from .embedder import Embedder
from .indexer import FAISSIndexer


class Retriever:

    def __init__(
        self,
        index_path: str = "",
        embedder: Optional[Embedder] = None,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ):
        self.index_path = index_path or settings.KNOWLEDGE_INDEX_PATH
        self.embedder = embedder or Embedder()
        self.top_k = top_k or settings.RAG_TOP_K
        # L2 距离越小越相似，低于 threshold 的视为不相关
        self.score_threshold = score_threshold if score_threshold is not None else settings.RAG_SCORE_THRESHOLD
        self._indexer: Optional[FAISSIndexer] = None

    def _ensure_loaded(self):
        if self._indexer is None:
            self._indexer = FAISSIndexer()
            self._indexer.load(self.index_path)

    def retrieve(self, query: str) -> list[str]:
        """
        检索相关 chunks（L2 距离越小越相似，>= threshold 的视为噪声丢弃）。

        注意：bge-large-zh 的 L2 距离通常 > 80，默认 threshold=120 是合理的。
        如果检索结果太少，可以调大 threshold。
        """
        try:
            self._ensure_loaded()
        except (FileNotFoundError, RuntimeError):
            return []

        query_embedding = self.embedder.encode_single(query)
        results = self._indexer.search(query_embedding, k=self.top_k)

        # L2 距离越大越不相似，只保留小于 threshold 的
        filtered = [chunk for chunk, score in results if score <= self.score_threshold]
        return filtered

    def retrieve_with_scores(self, query: str) -> list[tuple[str, float]]:
        """检索并返回 chunk + L2 距离分数"""
        try:
            self._ensure_loaded()
        except (FileNotFoundError, RuntimeError):
            return []

        query_embedding = self.embedder.encode_single(query)
        results = self._indexer.search(query_embedding, k=self.top_k)
        return [(chunk, score) for chunk, score in results if score <= self.score_threshold]


def build_index(
    documents: list[dict],
    output_path: str,
    embedder: Optional[Embedder] = None,
    index_type: str = "hnsw",
    chunk_max_chars: int = 500,
) -> FAISSIndexer:
    """从文档列表构建 FAISS 索引"""
    from .chunker import SessionChunker

    chunker = SessionChunker(max_chars=chunk_max_chars)
    chunks = chunker.chunk_documents(documents)
    chunk_texts = [c.content for c in chunks]

    embedder = embedder or Embedder()
    embeddings = embedder.encode(chunk_texts)

    indexer = FAISSIndexer(embedding_dim=embedder.embedding_dim, index_type=index_type)
    indexer.build(chunk_texts, embeddings)
    indexer.save(output_path)
    return indexer
