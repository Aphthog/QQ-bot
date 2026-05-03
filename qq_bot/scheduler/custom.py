from .base import BaseSource


class CustomSource(BaseSource):
    name = "custom"

    async def fetch(self) -> str:
        return "这是一条自定义广播消息"
