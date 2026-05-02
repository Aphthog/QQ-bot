"""
向量化：使用 bge-large-zh 将文本转为向量
中文场景用哈工大开源模型，CPU 可跑
"""

import os
from typing import Optional
import numpy as np

# 禁用 transformers 后台 safetensors 转换（避免联网校验 sha）
os.environ["HF_HUB_DISABLE_SAFETENSORS"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

# sentence-transformers 用于加载 bge-large-zh
try:
    from sentence_transformers import SentenceTransformer
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False


class Embedder:
    """
    向量化器，使用 bge-large-zh（哈工大开源，中文语义理解强，CPU 可跑）
    模型地址：https://huggingface.co/embed-multilingual
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-zh-v1.5",
        device: str = "cpu",
        batch_size: int = 8,
    ):
        """
        Args:
            model_name: 模型名称，默认 bge-large-zh-v1.5
            device: 设备，cpu 或 cuda
            batch_size: 批处理大小，控制每次向量化多少条
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: Optional["SentenceTransformer"] = None

    @property
    def model(self):
        """懒加载模型"""
        if self._model is None:
            if not _HAS_SENTENCE_TRANSFORMERS:
                raise RuntimeError(
                    "sentence-transformers 未安装，请运行: pip install sentence-transformers"
                )
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        将文本列表向量化

        Args:
            texts: 文本列表

        Returns:
            np.ndarray: 形状为 (len(texts), embedding_dim) 的向量数组
        """
        if not texts:
            return np.array([])

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,  # L2 归一化，利于余弦相似度
            show_progress_bar=False,
        )
        return np.array(embeddings)

    def encode_single(self, text: str) -> np.ndarray:
        """单条文本向量化"""
        return self.encode([text])[0]

    @property
    def embedding_dim(self) -> int:
        """返回向量维度"""
        # bge-large-zh v1.5 维度是 1024
        return 1024