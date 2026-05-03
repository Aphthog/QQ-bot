from abc import ABC, abstractmethod


class BaseSource(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> str:
        """返回要广播的内容文本"""
        ...
