"""
Tool Registry and Executor for the QQ bot agent.

Defines 8 tool schemas (OpenAI function-calling format), a handler registry
mapping each tool name to an async callable, and a parallel executor with
per-tool timeout protection and result sanitization.
"""

import asyncio
import logging

from qq_bot.agent.response import ToolCall
from qq_bot.agent.sanitize import sanitize_tool_result
from qq_bot.config import settings

logger = logging.getLogger("qq_bot.agent")

# ── Tool Schemas ──────────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索互联网获取最新信息，适合查新闻、实时数据、事件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询城市实时天气，返回温度、湿度、风速等信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，如 上海、北京"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "从已入库的知识库中检索相关信息。适合查之前存过的网页内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crawl_webpage",
            "description": "爬取指定网页的正文内容，返回清洗后的文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页URL，必须以 https:// 开头"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_knowledge",
            "description": "爬取网页内容并存入知识库，之后可通过 search_knowledge 检索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页URL，必须以 https:// 开头"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "使用 AI 生成图片。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "图片描述，中文或英文"},
                    "effect": {
                        "type": "string",
                        "description": "图片效果",
                        "enum": ["默认", "水平翻转", "左右对称", "上下对称", "旋转", "彩色化"],
                    },
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_speakers",
            "description": "查看本群今日发言排行榜 Top5。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "random_mention",
            "description": "从本群最近活跃用户中随机 @ 一人。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# ── Handler Implementations ───────────────────────────────────────────────────


async def _handle_search_web(params: dict, ctx: dict) -> str:
    from qq_bot.services.web_search import search_web_async

    query = params.get("query", "")
    if not query:
        return "[工具失败: 缺少 query 参数]"
    results = await search_web_async(query)
    return results if results else "[搜索无结果]"


async def _handle_get_weather(params: dict, ctx: dict) -> str:
    from qq_bot.skills.weather import WeatherSkill

    ws = WeatherSkill()
    return await ws.execute({"city": params.get("city", "")}, ctx)


async def _handle_search_knowledge(params: dict, ctx: dict) -> str:
    from qq_bot.rag.retriever import Retriever

    query = params.get("query", "")
    if not query:
        return "[工具失败: 缺少 query 参数]"
    try:
        retriever = Retriever()
        chunks = retriever.retrieve(query)
        if not chunks:
            return "[知识库中未找到相关内容]"
        return "\n\n".join(chunks[:5])
    except Exception:
        return "[知识库检索失败，可能索引尚未建立]"


async def _handle_crawl_webpage(params: dict, ctx: dict) -> str:
    from qq_bot.services.crawler import crawl_url_async
    from qq_bot.security.url_validator import URLValidationError, validate_url

    url = params.get("url", "")
    if not url:
        return "[工具失败: 缺少 url 参数]"
    try:
        validate_url(url)
    except URLValidationError as e:
        return f"[URL 校验失败: {e}]"
    content = await crawl_url_async(url)
    if not content:
        return "[网页获取失败，请检查URL是否正确]"
    return sanitize_tool_result(content)


async def _handle_add_to_knowledge(params: dict, ctx: dict) -> str:
    from qq_bot.skills.memory import MemorySkill
    from qq_bot.security.url_validator import URLValidationError, validate_url

    url = params.get("url", "")
    if not url:
        return "[工具失败: 缺少 url 参数]"
    try:
        validate_url(url)
    except URLValidationError as e:
        return f"[URL 校验失败: {e}]"
    ms = MemorySkill()
    return await ms.execute({"url": url}, ctx)


async def _handle_generate_image(params: dict, ctx: dict) -> str:
    from qq_bot.llm.image_gen import generate_image

    prompt = params.get("prompt", "")
    effect = params.get("effect", "")
    if effect and effect != "默认":
        prompt = f"基于以下内容{effect}：{prompt}，效果逼真"
    if not prompt:
        return "[工具失败: 缺少 prompt 参数]"
    result = await generate_image(prompt)
    if result.startswith("base64://"):
        return f"[图片已生成] {result}"
    return "[图片生成失败，请稍后重试]"


async def _handle_get_top_speakers(params: dict, ctx: dict) -> str:
    from qq_bot.skills.group_stats import GroupStatsSkill

    gs = GroupStatsSkill()
    return await gs.execute({}, ctx)


async def _handle_random_mention(params: dict, ctx: dict) -> str:
    from qq_bot.skills.random_mention import RandomMentionSkill

    rm = RandomMentionSkill()
    return await rm.execute({}, ctx)


# ── Tool Handler Registry ─────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "search_web": _handle_search_web,
    "get_weather": _handle_get_weather,
    "search_knowledge": _handle_search_knowledge,
    "crawl_webpage": _handle_crawl_webpage,
    "add_to_knowledge": _handle_add_to_knowledge,
    "generate_image": _handle_generate_image,
    "get_top_speakers": _handle_get_top_speakers,
    "random_mention": _handle_random_mention,
}

# ── Parallel Executor ─────────────────────────────────────────────────────────


async def execute_tool_calls(
    tool_calls: list[ToolCall],
    ctx: dict,
) -> list[dict]:
    """并行执行 tool_calls，返回 tool result 消息列表。每个 tool 有超时保护。"""

    async def _execute_one(tc: ToolCall) -> dict:
        handler = TOOL_HANDLERS.get(tc.name)
        if handler is None:
            return ToolCall.build_tool_result(
                tc.id, f"[工具 '{tc.name}' 不存在]"
            )

        merged_params = {**tc.arguments, **ctx}

        try:
            result = await asyncio.wait_for(
                handler(merged_params, ctx),
                timeout=settings.AGENT_TOOL_TIMEOUT,
            )
            return ToolCall.build_tool_result(tc.id, sanitize_tool_result(result))
        except asyncio.TimeoutError:
            return ToolCall.build_tool_result(
                tc.id, f"[工具 '{tc.name}' 执行超时]"
            )
        except Exception as e:
            logger.error(f"Tool '{tc.name}' failed: {e}", exc_info=True)
            return ToolCall.build_tool_result(
                tc.id, f"[工具 '{tc.name}' 执行异常: {type(e).__name__}]"
            )

    return await asyncio.gather(*[_execute_one(tc) for tc in tool_calls])
