"""Tool Registry with @tool decorator and parallel executor."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

from qq_bot.config import config

logger = logging.getLogger("qq_bot.tools")


class ToolInfo:
    __slots__ = ("name", "description", "params", "category", "require_auth", "handler")

    def __init__(
        self,
        name: str,
        description: str,
        params: dict[str, tuple[type, str]],
        category: str,
        require_auth: bool,
        handler: Callable,
    ):
        self.name = name
        self.description = description
        self.params = params
        self.category = category
        self.require_auth = require_auth
        self.handler = handler

    def to_openai_schema(self) -> dict[str, Any]:
        sig = inspect.signature(self.handler)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for pname, (ptype, pdesc) in self.params.items():
            json_type = "string" if ptype is str else "number" if ptype in (int, float) else "string"
            properties[pname] = {"type": json_type, "description": pdesc}
            param = sig.parameters.get(pname)
            if param is not None and param.default is inspect.Parameter.empty:
                required.append(pname)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    _tools: dict[str, ToolInfo] = {}

    @classmethod
    def register(cls, info: ToolInfo) -> None:
        if info.name in cls._tools:
            raise ValueError(f"Tool '{info.name}' already registered")
        cls._tools[info.name] = info

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any]:
        if name not in cls._tools:
            raise ValueError(f"Unknown tool: {name}")
        return cls._tools[name].to_openai_schema()

    @classmethod
    def get_all_schemas(cls, for_user: bool = False) -> list[dict[str, Any]]:
        schemas = []
        for t in cls._tools.values():
            if for_user and t.category == "admin":
                continue
            schemas.append(t.to_openai_schema())
        return schemas

    @classmethod
    async def execute(cls, name: str, arguments: dict[str, Any], ctx: dict[str, Any]) -> str:
        if name not in cls._tools:
            return f"[工具 '{name}' 不存在]"
        info = cls._tools[name]
        merged = {**ctx, **arguments}
        try:
            result = await asyncio.wait_for(
                info.handler(**{k: v for k, v in merged.items() if k in info.params}),
                timeout=config.AGENT_TOOL_TIMEOUT,
            )
            return str(result) if result is not None else ""
        except asyncio.TimeoutError:
            return f"[工具 '{name}' 执行超时]"
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
            return f"[工具 '{name}' 执行异常: {type(e).__name__}]"

    @classmethod
    async def execute_all(
        cls, tool_calls: list[dict[str, Any]], ctx: dict[str, Any]
    ) -> list[dict[str, Any]]:
        async def _exec_one(tc: dict[str, Any]) -> dict[str, Any]:
            result = await cls.execute(tc["name"], tc.get("arguments", {}), ctx)
            return {
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result,
            }
        return await asyncio.gather(*[_exec_one(tc) for tc in tool_calls])


def tool(
    name: str,
    description: str,
    params: dict[str, tuple[type, str]],
    *,
    category: str = "core",
    require_auth: bool = False,
):
    """Decorator: register an async function as an agent tool."""
    def decorator(fn: Callable):
        info = ToolInfo(
            name=name,
            description=description,
            params=params,
            category=category,
            require_auth=require_auth,
            handler=fn,
        )
        ToolRegistry.register(info)
        return fn
    return decorator
