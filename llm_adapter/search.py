"""
联网搜索模块
"""
import os
import asyncio
from typing import Optional

try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    _DDGS_AVAILABLE = False


def search_web(query: str, max_results: int = 5) -> str:
    """
    联网搜索，返回格式化结果

    Args:
        query: 搜索关键词
        max_results: 最大结果数

    Returns:
        格式化后的搜索结果，空或失败返回空字符串
    """
    if not _DDGS_AVAILABLE:
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

        if not results:
            return ""
        return "\n\n".join(results)
    except Exception:
        return ""


async def search_web_async(query: str, max_results: int = 5) -> str:
    """异步搜索（DDGS 是同步的，用线程池包装）"""
    return await asyncio.to_thread(search_web, query, max_results)


# 需要联网搜索的关键字，满足任一条件就搜
_SEARCH_TRIGGERS = [
    "今天", "昨天", "明天", "现在", "最近",
    "最新", "今日", "此时此刻",
    "天气", "气温", "温度", "新闻",
    "热搜", "排行榜", "排名",
    "股价", "股价", "指数",
    "比赛", "结果", "赛程",
    "开奖", "中奖", "彩票",
]


def should_search(query: str) -> bool:
    """判断是否需要联网搜索"""
    enabled = os.getenv("ENABLE_WEB_SEARCH", "false")
    print(f"[SEARCH DEBUG] ENABLE_WEB_SEARCH={repr(enabled)}", flush=True)
    if enabled.lower() != "true":
        return False
    q = query.lower()
    return any(t in q for t in _SEARCH_TRIGGERS)


def build_search_context(query: str, max_results: int = 5) -> str:
    """构建搜索上下文（仅搜索相关问题时调用）"""
    results = search_web(query, max_results)
    if not results:
        return ""
    return f"\n\n【网络搜索结果】\n{results}\n\n请基于以上搜索结果回答用户问题。"
