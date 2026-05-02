"""
索引器：使用 FAISS 构建向量索引
支持 IndexFlatL2（简单粗暴）和 HNSW（更优）
"""

import os
import pickle
from typing import Optional
import numpy as np

try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False


class FAISSIndexer:
    """
    FAISS 向量索引构建器
    支持两种索引类型：
    - IndexFlatL2：暴力检索，简单但准确，适合小规模（< 10000）
    - HNSW：近似最近邻，O(log N) 复杂度，适合大规模
    """

    def __init__(
        self,
        embedding_dim: int = 1024,
        index_type: str = "flat",
        hnsw_m: int = 32,
        hnsw_ef: int = 200,
    ):
        """
        Args:
            embedding_dim: 向量维度
            index_type: 索引类型，flat 或 hnsw
            hnsw_m: HNSW 参数，每层连接数，越大越精确但越慢
            hnsw_ef: HNSW 构建参数，越大越精确但越慢
        """
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        self.hnsw_m = hnsw_m
        self.hnsw_ef = hnsw_ef
        self._index: Optional["faiss.Index"] = None
        self._chunks: list = []  # 存储 chunk 原始文本，用于召回

    def build(self, chunks: list, embeddings: np.ndarray):
        """
        从 chunks 和 embeddings 构建索引

        Args:
            chunks: chunk 列表（与 embeddings 一一对应）
            embeddings: numpy 数组，形状 (n, embedding_dim)
        """
        if not _HAS_FAISS:
            raise RuntimeError("faiss 未安装，请运行: pip install faiss-cpu 或 faiss-gpu")

        if len(chunks) != embeddings.shape[0]:
            raise ValueError(f"chunks 数量 {len(chunks)} 与 embeddings 数量 {embeddings.shape[0]} 不匹配")

        n = len(chunks)
        dim = embeddings.shape[1]

        # 根据类型创建索引
        if self.index_type == "flat":
            index = faiss.IndexFlatL2(dim)
        elif self.index_type == "hnsw":
            index = faiss.IndexHNSWFlat(dim, self.hnsw_m)
            index.hnsw.efConstruction = self.hnsw_ef
        else:
            raise ValueError(f"不支持的索引类型: {self.index_type}")

        # 添加向量
        index.add(embeddings.astype(np.float32))

        self._index = index
        self._chunks = list(chunks)

    def save(self, path: str):
        """
        保存索引和 chunks 到本地

        Args:
            path: 保存路径（不带扩展名，会生成 .index 和 .pkl 两个文件）
        """
        if self._index is None:
            raise RuntimeError("索引未构建，无法保存")

        # 保存 FAISS 索引
        index_path = f"{path}.index"
        faiss.write_index(self._index, index_path)

        # 保存 chunks 元数据
        meta_path = f"{path}.pkl"
        with open(meta_path, "wb") as f:
            pickle.dump(self._chunks, f)

    def load(self, path: str):
        """
        从本地加载索引

        Args:
            path: 保存路径（不带扩展名）
        """
        if not _HAS_FAISS:
            raise RuntimeError("faiss 未安装，请运行: pip install faiss-cpu 或 faiss-gpu")

        index_path = f"{path}.index"
        meta_path = f"{path}.pkl"

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"索引文件不存在: {index_path}")

        self._index = faiss.read_index(index_path)

        with open(meta_path, "rb") as f:
            self._chunks = pickle.load(f)

    @property
    def index(self):
        """获取索引对象"""
        if self._index is None:
            raise RuntimeError("索引未加载，请先调用 load() 或 build()")
        return self._index

    @property
    def chunks(self) -> list:
        """获取所有 chunks"""
        return self._chunks

    @property
    def chunk_count(self) -> int:
        """chunks 数量"""
        return len(self._chunks)

    def add(self, chunks: list, embeddings: np.ndarray):
        """
        向已有索引追加新的 chunks 和 embeddings

        Args:
            chunks: chunk 列表
            embeddings: numpy 数组，形状 (n, embedding_dim)
        """
        if self._index is None:
            raise RuntimeError("索引未构建，请先调用 build()")

        if len(chunks) != embeddings.shape[0]:
            raise ValueError(f"chunks 数量 {len(chunks)} 与 embeddings 数量 {embeddings.shape[0]} 不匹配")

        self._index.add(embeddings.astype(np.float32))
        self._chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, k: int = 5, ef_search: int = 512) -> list[tuple]:
        """
        检索 Top-K 最相似的 chunk

        Args:
            query_embedding: 查询向量，形状 (embedding_dim,)
            k: 返回数量
            ef_search: HNSW 搜索参数，越大越精确但越慢（仅 HNSW 有效）

        Returns:
            list[tuple]: [(chunk, score), ...]，按相似度从高到低排序
        """
        if self._index is None:
            raise RuntimeError("索引未加载")

        # 如果是 HNSW 索引，设置搜索参数
        if self.index_type == "hnsw" and ef_search:
            self._index.hnsw.efSearch = ef_search

        # 搜索
        query = query_embedding.astype(np.float32).reshape(1, -1)
        distances, indices = self._index.search(query, k)

        # 组装结果 [(chunk, score), ...]
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self._chunks):
                results.append((self._chunks[idx], float(dist)))

        return results