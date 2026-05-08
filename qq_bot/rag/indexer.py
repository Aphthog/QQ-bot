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

    def __init__(
        self,
        embedding_dim: int = 1024,
        index_type: str = "flat",
        hnsw_m: int = 32,
        hnsw_ef: int = 200,
    ):
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        self.hnsw_m = hnsw_m
        self.hnsw_ef = hnsw_ef
        self._index: Optional["faiss.Index"] = None
        self._chunks: list = []

    def build(self, chunks: list, embeddings: np.ndarray):
        if not _HAS_FAISS:
            raise RuntimeError("请安装: pip install faiss-cpu")
        if len(chunks) != embeddings.shape[0]:
            raise ValueError("chunks 与 embeddings 数量不匹配")

        dim = embeddings.shape[1]
        if self.index_type == "flat":
            index = faiss.IndexFlatL2(dim)
        elif self.index_type == "hnsw":
            index = faiss.IndexHNSWFlat(dim, self.hnsw_m)
            index.hnsw.efConstruction = self.hnsw_ef
        else:
            raise ValueError(f"不支持的索引类型: {self.index_type}")

        index.add(embeddings.astype(np.float32))
        self._index = index
        self._chunks = list(chunks)

    def save(self, path: str):
        if self._index is None:
            raise RuntimeError("索引未构建")
        faiss.write_index(self._index, f"{path}.index")
        with open(f"{path}.pkl", "wb") as f:
            pickle.dump(self._chunks, f)

    def load(self, path: str):
        if not _HAS_FAISS:
            raise RuntimeError("请安装: pip install faiss-cpu")
        if not os.path.exists(f"{path}.index"):
            raise FileNotFoundError(f"索引文件不存在: {path}.index")
        self._index = faiss.read_index(f"{path}.index")
        with open(f"{path}.pkl", "rb") as f:
            self._chunks = pickle.load(f)

    @property
    def index(self):
        if self._index is None:
            raise RuntimeError("索引未加载，请先调用 load() 或 build()")
        return self._index

    @property
    def chunks(self) -> list:
        return self._chunks

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def add(self, chunks: list, embeddings: np.ndarray):
        if self._index is None:
            raise RuntimeError("索引未构建")
        if len(chunks) != embeddings.shape[0]:
            raise ValueError("chunks 与 embeddings 数量不匹配")
        self._index.add(embeddings.astype(np.float32))
        self._chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, k: int = 5, ef_search: int = 512) -> list[tuple]:
        if self._index is None:
            raise RuntimeError("索引未加载")
        if self.index_type == "hnsw" and ef_search:
            self._index.hnsw.efSearch = ef_search

        query = query_embedding.astype(np.float32).reshape(1, -1)
        distances, indices = self._index.search(query, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self._chunks):
                results.append((self._chunks[idx], float(dist)))
        return results
