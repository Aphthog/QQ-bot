"""
向量化：使用 bge-large-zh 将文本转为向量。
"""

import os
from typing import Optional

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SAFETENSORS", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


class Embedder:
    """向量化器（bge-large-zh-v1.5，1024维）"""

    _sentence_transformers_available = False

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        device: str = "cpu",
        batch_size: int = 8,
    ):
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: Optional = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise RuntimeError("请安装: pip install sentence-transformers")
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.array([])
        return np.array(
            self.model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        )

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

    @property
    def embedding_dim(self) -> int:
        return 1024
