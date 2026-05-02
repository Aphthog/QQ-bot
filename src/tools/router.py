"""
工具路由：将用户查询分发到合适的工具适配器
"""
from typing import Optional
from . import Tool


class ToolRouter:
    """工具路由"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRouter":
        """注册工具，返回 self 支持链式调用"""
        self._tools[tool.tool_id] = tool
        return self

    def route(self, query: str) -> str:
        """
        执行路由，返回所有触发工具的上下文拼接

        Args:
            query: 用户原始 query

        Returns:
            拼接后的上下文字符串，无结果返回空字符串
        """
        if not query:
            return ""

        contexts = []
        for tool in self._tools.values():
            if tool.should_use(query):
                ctx = tool.get_context(query)
                if ctx:
                    contexts.append(tool._wrap_context(ctx))

        return "\n\n".join(contexts)

    def list_tools(self) -> list[dict]:
        """列出所有已注册工具"""
        return [
            {"tool_id": t.tool_id, "name": t.name}
            for t in self._tools.values()
        ]


# === 全局单例 ===
_router: Optional[ToolRouter] = None


def get_router() -> ToolRouter:
    global _router
    if _router is None:
        _router = ToolRouter()
        # 默认注册适配器
        from .adapters import RAGAdapter, SearchAdapter

        _router.register(RAGAdapter())
        _router.register(SearchAdapter())
    return _router
