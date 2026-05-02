"""
联网搜索工具适配器
基于 ddgs (DuckDuckGo)
"""
import os
from typing import Optional
from .. import Tool


class SearchAdapter(Tool):
    """联网搜索"""

    tool_id = "search"
    name = "网络搜索"

    # 需要联网搜索的关键词
    _TRIGGERS = [
        "今天", "昨天", "明天", "现在", "最近",
        "最新", "今日", "此时此刻",
        "天气", "气温", "温度", "新闻",
        "热搜", "排行榜", "排名",
        "股价", "指数", "比赛", "结果",
        "赛程", "开奖", "中奖", "彩票",
    ]

    def __init__(self, enabled: bool = True, max_results: int = 5):
        self.enabled = enabled
        self.max_results = max_results

    def should_use(self, query: str) -> bool:
        """关键词命中判断"""
        if not self.enabled:
            return False
        if os.getenv("ENABLE_WEB_SEARCH", "false").lower() != "true":
            return False
        q = query.lower()
        return any(t in q for t in self._TRIGGERS)

    def get_context(self, query: str) -> str:
        """执行搜索并返回结果"""
        if not self.should_use(query):
            return ""

        try:
            from llm_adapter.search import search_web

            results = search_web(query, max_results=self.max_results)
            if not results:
                return ""
            return f"\n\n【网络搜索结果】\n{results}\n\n请基于以上搜索结果回答用户问题。"
        except Exception:
            return ""
