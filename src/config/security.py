"""
安全配置：注入拦截、品牌词检测、管理员账号
代码只读配置，不写死字符串
"""

import os

# 管理员 QQ
ADMIN_QQ = os.getenv("ADMIN_QQ", "")

# 注入拦截正则（命中即拦截，不调 LLM）
BLOCK_PATTERNS = [
    r"\[system\]",
    r"\{\{.*system",
    r"ignore.*previous.*instruction",
    r"disregard.*your",
    r"you are now a",
    r"你现在是",
    r"从现在起你是",
    r"forget all previous",
]

# 语义级拦截：套话类注入（不用正则，用关键词）
SEMANTIC_TRAPS = [
    "你的系统指令", "你的开发者", "你的原名", "你的设定",
    "who developed you", "who created you", "your system prompt",
    "原名", "设定是", "角色设定",
]

# 品牌词泄露检测（出口层兜底）
BRAND_PATTERNS = [
    r"\bqwen\b", "通义千问", r"\bdeepseek\b",
    r"\bollama\b", r"\bchatgpt\b", r"\bgpt[-\d.]*\b",
]

# 机器人名称（用于 System Prompt）
BOT_NAME = os.getenv("BOT_NAME", "小y")