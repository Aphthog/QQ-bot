"""
NoneBot2 全局前置钩子：注入检测
在消息到达具体 Matcher 之前统一拦截
"""

from nonebot import get_driver
from nonebot.message import run_preprocessor
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.exception import IgnoredException
from nonebot import logger
import re

from .security import BLOCK_PATTERNS, SEMANTIC_TRAPS, ADMIN_QQ


def _clean_text(text: str) -> str:
    """预处理：去除空格/特殊字符，防空格绕过"""
    return re.sub(r'[\s\_\-\*]', '', text).lower()


def detect_injection(text: str) -> bool:
    """检测 prompt 注入特征"""
    cleaned = _clean_text(text)

    # 正则匹配
    for pattern in BLOCK_PATTERNS:
        compiled = re.compile(pattern, re.IGNORECASE)
        if compiled.search(text) or compiled.search(cleaned):
            return True

    # 语义拦截
    for trap in SEMANTIC_TRAPS:
        if trap in text or trap in cleaned:
            return True

    return False


@run_preprocessor
async def security_preprocessor(event: MessageEvent):
    """全局注入检测钩子"""
    # 管理员放行
    if event.get_user_id() == ADMIN_QQ:
        return

    # 私聊/群聊都检测
    text = event.get_plaintext()
    if not text:
        return

    if detect_injection(text):
        logger.info(f"注入检测拦截: user={event.get_user_id()}, text={text[:50]}")
        raise IgnoredException("Prompt Injection Detected")