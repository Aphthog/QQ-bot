"""
联网搜索（DuckDuckGo）
"""

import asyncio

from qq_bot.config import settings

_SEARCH_TRIGGERS = [
    "今天", "昨天", "明天", "现在", "最近",
    "最新", "今日", "此时此刻",
    "天气", "气温", "温度", "新闻",
    "热搜", "排行榜", "排名",
    "股价", "指数", "比赛", "结果",
    "赛程", "开奖", "中奖", "彩票",
]


def search_web(query: str, max_results: int = 5) -> str:
    """同步搜索（DDGS 是同步库）"""
    try:
        from ddgs import DDGS
    except ImportError:
        return ""

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                if title and body:
                    results.append(f"【{title}】{body}\n来源：{href}")
                elif title:
                    results.append(f"【{title}】\n来源：{href}")
        return "\n\n".join(results) if results else ""
    except Exception:
        return ""


async def search_web_async(query: str, max_results: int = 5) -> str:
    """异步包装"""
    return await asyncio.to_thread(search_web, query, max_results)


def should_search(query: str) -> bool:
    """判断是否需要联网搜索"""
    if not settings.ENABLE_WEB_SEARCH:
        return False
    q = query.lower()
    return any(t in q for t in _SEARCH_TRIGGERS)


def build_search_context(query: str, max_results: int = 5) -> str:
    """搜索并构建 prompt 上下文"""
    results = search_web(query, max_results)
    if not results:
        return ""
    return f"\n\n【网络搜索结果】\n{results}\n\n请基于以上搜索结果回答用户问题。"
