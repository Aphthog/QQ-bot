"""
调试日志：记录请求 → 上下文 → LLM 响应 → 回复的完整链路。
通过 DEBUG_MODE=true 启用。
"""

import logging
import json

from qq_bot.config import settings

logger = logging.getLogger("qq_bot.debug")

_configured = False


def _setup():
    global _configured
    if _configured:
        return
    _configured = True
    if not settings.DEBUG_MODE:
        logger.addHandler(logging.NullHandler())
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def incoming(source: str, user_id: str, text: str, image: bool = False):
    _setup()
    if not settings.DEBUG_MODE:
        return
    img = " [图片]" if image else ""
    logger.debug(f"→ {source} from {user_id}: {text[:200]}{img}")


def context(msgs: list[dict]):
    _setup()
    if not settings.DEBUG_MODE:
        return
    n = len(msgs)
    logger.debug(f"  ctx: {n}条消息")
    for i, m in enumerate(msgs[-3:], max(1, n - 2)):
        content = m.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)[:100]
        elif isinstance(content, str):
            content = content[:200]
        logger.debug(f"    [{m.get('role')}] {content}")


def llm_req(system_prompt: str, prompt: str):
    _setup()
    if not settings.DEBUG_MODE:
        return
    logger.debug(f"  system: {system_prompt[:100]}...")
    logger.debug(f"  user: {prompt[:200]}")


def llm_resp(text: str):
    _setup()
    if not settings.DEBUG_MODE:
        return
    logger.debug(f"  llm → {text[:300]}")


def outgoing(text: str, image_url: str | None = None):
    _setup()
    if not settings.DEBUG_MODE:
        return
    img = f" [图片: {image_url[:80]}]" if image_url else ""
    logger.debug(f"← {text[:200]}{img}")


def skill(name: str, params: dict, result: str):
    _setup()
    if not settings.DEBUG_MODE:
        return
    logger.debug(f"  skill: /{name} {json.dumps(params, ensure_ascii=False)[:100]}")
    logger.debug(f"  skill → {result[:200]}")


def sanitized(reason: str):
    _setup()
    if not settings.DEBUG_MODE:
        return
    logger.debug(f"  ⚠ sanitized: {reason}")
