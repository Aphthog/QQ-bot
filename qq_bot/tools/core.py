"""Core agent tools: web_search, web_fetch, run_code."""
from __future__ import annotations

import asyncio
import io
import logging
import re
import sys
import traceback

import httpx

from qq_bot.config import config
from qq_bot.security.url_validator import URLValidationError, validate_url
from qq_bot.tools.registry import tool

logger = logging.getLogger("qq_bot.tools.core")


# ── web_search ──────────────────────────────────────────────

@tool(
    name="web_search",
    description="搜索互联网获取实时信息。适用：查新闻、天气、股价、百科、实时数据等。",
    params={"query": (str, "搜索关键词，中文或英文")},
    category="core",
)
async def web_search(query: str) -> str:
    if not query or not query.strip():
        return "[搜索失败: 缺少搜索关键词]"

    backend = config.SEARCH_BACKEND
    if backend == "searxng":
        return await _search_searxng(query)
    elif backend == "tavily":
        return await _search_tavily(query)
    return f"[搜索失败: 未知搜索后端 '{backend}']"


async def _search_searxng(query: str, max_results: int = 5) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{config.SEARXNG_BASE_URL}/search",
                params={"q": query, "format": "json", "categories": "general"},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])[:max_results]
            if not results:
                return "[搜索无结果]"
            lines = []
            for r in results:
                title = r.get("title", "")
                snippet = r.get("content", "") or r.get("snippet", "")
                url = r.get("url", "")
                lines.append(f"[{title}]\n{snippet}\n来源: {url}")
            return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"SearXNG search failed: {e}")
        return f"[搜索失败: {e}]"


async def _search_tavily(query: str, max_results: int = 5) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": config.TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return "[搜索无结果]"
            lines = []
            for r in results:
                lines.append(f"[{r.get('title', '')}]\n{r.get('content', '')}\n来源: {r.get('url', '')}")
            return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return f"[搜索失败: {e}]"


# ── web_fetch ───────────────────────────────────────────────

@tool(
    name="web_fetch",
    description="抓取网页正文内容。适用：打开搜索结果链接、读取文章全文。",
    params={"url": (str, "网页URL，必须以 https:// 开头")},
    category="core",
)
async def web_fetch(url: str) -> str:
    if not url or not url.strip():
        return "[抓取失败: 缺少URL]"
    try:
        validate_url(url)
    except URLValidationError as e:
        return f"[URL校验失败: {e}]"

    try:
        from qq_bot.services.crawler import crawl_url_async
        content = await crawl_url_async(url)
        if not content:
            return "[抓取失败: 网页内容为空]"
        if len(content) > 2000:
            content = content[:2000]
        return content
    except Exception as e:
        logger.error(f"web_fetch failed for {url}: {e}")
        return f"[抓取失败: {e}]"


# ── run_code ────────────────────────────────────────────────

FORBIDDEN_MODULES = {"os", "subprocess", "shutil", "sys", "socket", "ctypes", "__builtins__"}

CODE_TIMEOUT = 5  # seconds


@tool(
    name="run_code",
    description="执行Python代码进行计算或数据分析。适用：数学计算、数据处理、简单图表。",
    params={"code": (str, "要执行的Python代码")},
    category="core",
)
async def run_code(code: str) -> str:
    if not code or not code.strip():
        return "[代码执行: 代码为空]"

    # Security: block forbidden imports
    for mod in FORBIDDEN_MODULES:
        if re.search(rf"\bimport\s+{mod}\b", code) or re.search(rf"\bfrom\s+{mod}\b", code):
            return f"[代码执行: 禁止导入模块 '{mod}']"

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        def _safe_import(name, *args, **kwargs):
            if name in FORBIDDEN_MODULES:
                raise ImportError(f"import of '{name}' is forbidden")
            return __import__(name, *args, **kwargs)

        exec_globals: dict = {"__builtins__": {
            "print": print, "len": len, "range": range,
            "int": int, "float": float, "str": str, "list": list,
            "dict": dict, "set": set, "tuple": tuple, "bool": bool,
            "sum": sum, "min": min, "max": max, "abs": abs,
            "sorted": sorted, "enumerate": enumerate, "zip": zip,
            "round": round, "isinstance": isinstance, "type": type,
            "__import__": _safe_import,
        }}

        await asyncio.wait_for(
            asyncio.to_thread(exec, code, exec_globals),
            timeout=CODE_TIMEOUT,
        )

        output = stdout_capture.getvalue()
        errors = stderr_capture.getvalue()
        if errors:
            return f"[代码输出]\n{output}\n[错误]\n{errors}" if output else f"[コード错误]\n{errors}"
        return output if output.strip() else "[代码执行完毕，无输出]"

    except asyncio.TimeoutError:
        return "[代码执行超时]"
    except Exception:
        tb = traceback.format_exc()
        return f"[代码异常]\n{tb}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
