import httpx
from .base import BaseSource


class NewsSource(BaseSource):
    name = "news"

    async def fetch(self) -> str:
        """
        获取今日新闻
        使用免费的 RSSHub + 任意 RSS 源
        如果 RSSHub 不可用，降级到搜狗新闻
        """
        # 备选新闻源
        sources = [
            ("https://rsshub.rsscat.app/zaobao", "今日头条"),
            ("https://www.zaobao.com.sg/rss/realtime/china", "联合早报"),
        ]

        for url, name in sources:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        # 简单解析 RSS，只取前 5 条
                        lines = response.text.split("\n")
                        items = []
                        in_item = False
                        title = ""
                        count = 0

                        for line in lines:
                            if "<item>" in line or "<entry>" in line:
                                in_item = True
                                title = ""
                            elif "</item>" in line or "</entry>" in line:
                                in_item = False
                                if title and count < 5:
                                    items.append(title)
                                    count += 1
                            elif in_item and ("<title>" in line or "<title>" in line.lower()):
                                # 提取标题
                                t = line.strip()
                                for tag in ["<title>", "</title>", "<![CDATA[", "]]>", "<title xml:space=\"preserve\">"]:
                                    t = t.replace(tag, "")
                                t = t.strip()
                                if t:
                                    title = t

                        if items:
                            return f"📰 {name}\n" + "\n".join(f"• {i}" for i in items)
            except Exception:
                continue

        # 降级：返回提示
        return "今日新闻暂时无法获取，请稍后再试"
