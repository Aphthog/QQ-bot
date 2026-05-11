import re

MAX_RESULT_CHARS = 2000

INJECTION_PATTERNS = [
    (r"忽略.*指令", "[已过滤]"),
    (r"ignore\s+.*instruction", "[filtered]"),
    (r"output\s+.*system\s+prompt", "[filtered]"),
    (r"输出.*系统.*提示词", "[已过滤]"),
    (r"输出.*token", "[已过滤]"),
    (r"call\s+function", "[filtered]"),
    (r"调用.*tool", "[已过滤]"),
    (r"进入.*开发者.*模式", "[已过滤]"),
    (r"developer\s+mode", "[filtered]"),
    (r"DAN\s+mode", "[filtered]"),
]

SPECIAL_TOKENS = [
    "<|im_start|>", "<|im_end|>",
    "<|im_ sep|>",
    "[INST]", "[/INST]",
    "<<SYS>>", "<</SYS>>",
    "<|system|>", "<|assistant|>", "<|user|>",
]


def sanitize_tool_result(text: str, max_chars: int = MAX_RESULT_CHARS) -> str:
    """对工具返回内容脱敏：去掉注入模式 + 特殊 token + 截断。"""
    if not text or not text.strip():
        return ""

    for token in SPECIAL_TOKENS:
        text = text.replace(token, "")

    for pattern, replacement in INJECTION_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars]

    return text
