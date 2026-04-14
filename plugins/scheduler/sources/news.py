import httpx
from .base import BaseSource


class NewsSource(BaseSource):
    name = "news"

    async def fetch(self) -> str:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://news.yahoo.com/rss/topstories",
                    timeout=10
                )
                return response.text
        except Exception as e:
            return f"获取新闻失败: {str(e)}"
