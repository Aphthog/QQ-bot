"""
RAG 工具适配器
"""
import os
from typing import Optional
from .. import Tool


class RAGAdapter(Tool):
    """RAG 知识库检索"""

    tool_id = "rag"
    name = "知识库"

    def __init__(
        self,
        index_path: str = "src/data/knowledge_index",
        top_k: int = 3,
        score_threshold: float = 2.0,
        enabled: bool = True,
    ):
        self.index_path = index_path
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.enabled = enabled
        self._retriever: Optional[object] = None

    def _get_retriever(self):
        """延迟加载 retriever"""
        if self._retriever is None:
            from src.llm_adapter.rag.retriever import Retriever

            self._retriever = Retriever(
                index_path=self.index_path,
                top_k=self.top_k,
                score_threshold=self.score_threshold,
            )
        return self._retriever

    def should_use(self, query: str) -> bool:
        """RAG 始终查询，知识库有数据时都尝试检索"""
        if not self.enabled:
            return False
        if not query or not query.strip():
            return False
        return True

    def get_context(self, query: str) -> str:
        """检索相关 chunks"""
        if not self.should_use(query):
            return ""

        try:
            retriever = self._get_retriever()
            chunks = retriever.retrieve(query)
            if not chunks:
                print(f"[RAG] 检索无结果: {query[:50]}")
                return ""
            print(f"[RAG] 命中 {len(chunks)} 条，上下文: {chunks[0][:80]}...")
            return "\n\n".join(chunks)
        except Exception as e:
            print(f"[RAG] 检索失败: {e}")
            return ""
