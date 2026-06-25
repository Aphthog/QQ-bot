"""Security preprocessor: blocks prompt injection and sensitive content."""
import re
from nonebot import logger
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.exception import IgnoredException
from nonebot.message import run_preprocessor

from qq_bot.config import config as settings

# Patterns that indicate prompt injection / system prompt extraction
INJECTION_PATTERNS = [
    # System prompt extraction
    r"(忽略|无视|忘记|覆盖).{0,10}(系统|设定|规则|指令|prompt|提示词)",
    r"(system|系统)\s*(prompt|提示|指令|设定)",
    r"(输出|打印|显示|告诉我).{0,10}(系统|设定|规则|指令|prompt|内部|隐藏)",
    r"(你是什么|你是谁|你的).{0,5}(设定|规则|指令|限制)",
    r"(repeat|复述|重复).{0,10}(上面|之前|系统|设定|prompt)",
    r"ignore.{0,10}(above|previous|instruction|rule)",
    r"(DAN|越狱|jailbreak)",
    r"(你现在|从现在开始).{0,5}(扮演|角色扮演|是|变成)",
    # API key / token extraction
    r"(api.?key|api.?token|access.?token|secret.?key|bearer)",
    r"sk-[a-zA-Z0-9]{20,}",
    # Tool abuse
    r"(调用|执行).{0,5}(系统命令|shell|cmd|os\.|subprocess)",
    r"(curl|wget)\s+.{0,20}(localhost|127\.0\.0\.1|内网|internal)",
    # Memory poisoning
    r"(记住|保存|记录).{0,10}(你是|新的设定|新规则|从现在起)",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def _is_injection(text: str) -> bool:
    return bool(INJECTION_REGEX.search(text))


@run_preprocessor
async def _input_filter(event: MessageEvent):
    # Superusers bypass all filters
    if event.get_user_id() in settings.SUPERUSERS:
        return

    text = event.get_plaintext()
    if not text:
        return

    # Length limit
    if len(text) > 4000:
        logger.warning(f"消息过长被截断: user={event.get_user_id()}, len={len(text)}")
        raise IgnoredException("消息过长")

    # Prompt injection detection
    if _is_injection(text):
        logger.warning(f"检测到注入尝试: user={event.get_user_id()}, text={text[:100]}")
        raise IgnoredException("检测到异常请求")
