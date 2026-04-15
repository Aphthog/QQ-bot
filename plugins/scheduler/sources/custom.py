from .base import BaseSource


class CustomSource(BaseSource):
    name = "custom"

    async def fetch(self) -> str:
        """返回自定义内容（可配置）"""
        return "这是一条自定义广播消息"
