"""
分块器：按会话窗口切分文本
每个 chunk 是语义完整的最小单元，不是固定字数切
"""

from dataclasses import dataclass
from typing import Iterator


@dataclass
class Chunk:
    content: str
    source: str  # 来源标识，如 URL 或文件路径
    index: int   # 在原文本中的位置序号


class SessionChunker:
    """
    按会话窗口分块，而非固定字数。
    切分规则：同一来源连续文本超过 max_chars，或者遇到明显断点（换行+空行）则切新块。
    """

    def __init__(self, max_chars: int = 500, overlap: int = 50):
        """
        Args:
            max_chars: 单个 chunk 最大字符数
            overlap: 相邻 chunk 之间的重叠字符数（保持语义连贯）
        """
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk_text(self, text: str, source: str = "document") -> list[Chunk]:
        """
        将长文本切分为多个 chunk

        Args:
            text: 待切分文本
            source: 来源标识

        Returns:
            list[Chunk]: chunk 列表
        """
        if not text or not text.strip():
            return []

        chunks = []
        # 按段落分割（双换行或单换行）
        paragraphs = self._split_paragraphs(text)

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if not para.strip():
                continue

            # 如果单个段落就超过 max_chars，按句子切
            if len(para) > self.max_chars:
                if current_chunk:
                    chunks.append(Chunk(current_chunk, source, chunk_index))
                    chunk_index += 1
                    current_chunk = ""

                sub_chunks = self._split_long_paragraph(para)
                for sub in sub_chunks:
                    if sub.strip():
                        chunks.append(Chunk(sub, source, chunk_index))
                        chunk_index += 1
                continue

            # 加上当前段落是否会超过 max_chars
            if current_chunk and len(current_chunk) + len(para) > self.max_chars:
                chunks.append(Chunk(current_chunk.strip(), source, chunk_index))
                chunk_index += 1
                # 保留 overlap 保持连贯
                current_chunk = current_chunk[-self.overlap:] + para
            else:
                if current_chunk:
                    current_chunk += "\n" + para
                else:
                    current_chunk = para

        if current_chunk.strip():
            chunks.append(Chunk(current_chunk.strip(), source, chunk_index))

        return chunks

    def chunk_documents(self, documents: list[dict]) -> list[Chunk]:
        """
        批量分块：documents 格式 [{content: str, source: str}, ...]

        Args:
            documents: 文档列表

        Returns:
            list[Chunk]: 所有 chunk
        """
        all_chunks = []
        for doc in documents:
            content = doc.get("content", "")
            source = doc.get("source", "document")
            chunks = self.chunk_text(content, source)
            all_chunks.extend(chunks)
        return all_chunks

    def _split_paragraphs(self, text: str) -> list[str]:
        """按换行符分割段落"""
        return text.split("\n")

    def _split_long_paragraph(self, text: str) -> list[str]:
        """超长段落按句子切分"""
        # 按常见句号/问号/感叹号切分
        import re
        sentences = re.split(r'(?<=[。！？.?!])\s*', text)
        result = []
        current = ""

        for sent in sentences:
            if len(current) + len(sent) <= self.max_chars:
                current += sent
            else:
                if current:
                    result.append(current)
                current = sent

        if current:
            result.append(current)

        return result