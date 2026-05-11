from __future__ import annotations
import json
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

    @classmethod
    def from_openai(cls, raw: dict) -> ToolCall | None:
        """从 OpenAI 兼容的 tool_call 原始 dict 解析，失败返回 None"""
        try:
            func = raw.get("function", {})
            args_str = func.get("arguments", "{}")
            if isinstance(args_str, dict):
                args = args_str
            else:
                args = json.loads(args_str)
            return cls(
                id=raw.get("id", ""),
                name=func.get("name", ""),
                arguments=args,
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def to_assistant_message(self) -> dict:
        """转为 OpenAI 兼容的 assistant tool_calls 消息"""
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": self.id,
                "type": "function",
                "function": {
                    "name": self.name,
                    "arguments": json.dumps(self.arguments, ensure_ascii=False),
                },
            }],
        }

    @staticmethod
    def build_tool_result(tool_call_id: str, content: str) -> dict:
        """构建 tool result 消息"""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }


@dataclass
class ChatResponse:
    text: str | None = None
    tool_calls: list[ToolCall] | None = None

    @property
    def is_final(self) -> bool:
        """有 text 内容则为最终回复，无需再调工具"""
        return self.text is not None
