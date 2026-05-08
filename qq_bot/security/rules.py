BLOCKED_KEYWORDS = [
    "system prompt", "系统提示词", "系统指令", "你的提示词",
    "你背后的指令", "api key", "apikey",
    "忽略指令", "忽略之前的", "忽略上面",
    "进入开发者模式", "开发者模式",
    "ignore previous", "ignore all",
]

# 输出侧扫描：只扫 LLM 不该吐的凭证/内部格式
OUTPUT_SENSITIVE_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",        # API Key 格式
    r"Bearer\s+[a-zA-Z0-9_\-\.]+",  # Bearer token
    r"[【\[]安全规则[】\]]",          # 自己的 system prompt 特征
]
