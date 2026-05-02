"""
工具系统基类
所有工具适配器需实现 Tool 接口
"""
from abc import ABC, abstractmethod
from typing import Optional


class Tool(ABC):
    """工具基类"""

    tool_id: str = ""
    name: str = ""

    @abstractmethod
    def should_use(self, query: str) -> bool:
        """判断是否触发此工具"""
        pass

    @abstractmethod
    def get_context(self, query: str) -> str:
        """获取工具上下文，无结果返回空字符串"""
        pass

    def _wrap_context(self, content: str, prefix: str = "") -> str:
        """包装上下文，统一格式"""
        if not content:
            return ""
        if prefix:
            return f"【{self.name}】\n{content}"
        return content
