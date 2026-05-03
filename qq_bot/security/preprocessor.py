"""
前置过滤器：消息到达 matcher 前拦截敏感内容。
"""

import re
from nonebot import logger
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.exception import IgnoredException
from nonebot.message import run_preprocessor

from qq_bot.config import settings
from .rules import BLOCKED_KEYWORDS


def _is_sensitive(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in BLOCKED_KEYWORDS)


@run_preprocessor
async def _input_filter(event: MessageEvent):
    # 管理员放行
    if event.get_user_id() in settings.SUPERUSERS:
        return
    text = event.get_plaintext()
    if not text:
        return
    if _is_sensitive(text):
        logger.info(f"拦截敏感消息: user={event.get_user_id()}, text={text[:50]}")
        raise IgnoredException("Sensitive content blocked")
