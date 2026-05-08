from dataclasses import dataclass
import re


@dataclass
class Chunk:
    content: str
    source: str
    index: int


class SessionChunker:

    def __init__(self, max_chars: int = 500, overlap: int = 80):
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk_text(self, text: str, source: str = "document") -> list[Chunk]:
        if not text or not text.strip():
            return []

        chunks = []
        sentences = self._split_sentences(text)
        current = ""
        idx = 0

        for sent in sentences:
            if not sent.strip():
                continue

            if len(sent) > self.max_chars:
                if current.strip():
                    chunks.append(Chunk(current.strip(), source, idx))
                    idx += 1
                for sub in self._split_long_sentence(sent):
                    if sub.strip():
                        chunks.append(Chunk(sub.strip(), source, idx))
                        idx += 1
                current = ""
                continue

            if current and len(current) + len(sent) > self.max_chars:
                chunks.append(Chunk(current.strip(), source, idx))
                idx += 1
                current = current[-self.overlap:] + sent
            else:
                current = current + sent if current else sent

        if current.strip():
            chunks.append(Chunk(current.strip(), source, idx))

        return chunks

    def chunk_documents(self, documents: list[dict]) -> list[Chunk]:
        all_chunks = []
        for doc in documents:
            content = doc.get("content", "")
            source = doc.get("source", "document")
            all_chunks.extend(self.chunk_text(content, source))
        return all_chunks

    def _split_sentences(self, text: str) -> list[str]:
        """按中英文句号、问号、感叹号、换行切分"""
        return re.split(r'(?<=[。！？.!?\n])\s*', text)

    def _split_long_sentence(self, text: str) -> list[str]:
        """超长句子按逗号进一步切分"""
        parts = re.split(r'(?<=[，,;；])\s*', text)
        result = []
        current = ""
        for p in parts:
            if len(current) + len(p) <= self.max_chars:
                current += p
            else:
                if current:
                    result.append(current)
                current = p
        if current:
            result.append(current)
        return result
