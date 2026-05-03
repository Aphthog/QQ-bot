"""
技能系统：注册 + 命令路由 + 执行。
"""

import re

from .base import BaseSkill
from .memory import MemorySkill
from .weather import WeatherSkill
from .group_stats import GroupStatsSkill
from .random_mention import RandomMentionSkill

SKILLS = [
    {"name": "memory", "description": "将网页URL内容存入知识库，供后续检索使用。格式：/memory <网址>"},
    {"name": "weather", "description": "查询城市天气情况。格式：/weather <城市>"},
    {"name": "top", "description": "查看群聊发言排行榜，显示Top5发言最多的群友。格式：/top"},
    {"name": "random", "description": "从群聊最近活跃用户中随机艾特一人。格式：/random"},
]

_handlers: dict[str, BaseSkill] = {
    "memory": MemorySkill(),
    "weather": WeatherSkill(),
    "top": GroupStatsSkill(),
    "random": RandomMentionSkill(),
}

_param_patterns = {
    "memory": r"/memory\s+(.+)",
    "weather": r"/weather\s*(.+)",
    "top": r"/top",
    "random": r"/random",
}


def route_command(text: str) -> str | None:
    text = text.strip()
    # 标准化：去除前导 @机器人 和 / 后的空格
    text = re.sub(r'^@\S+\s*', '', text)
    text = re.sub(r'^/\s+', '/', text)
    for s in SKILLS:
        prefix = f"/{s['name']}"
        if not text.startswith(prefix):
            continue
        suffix = text[len(prefix):]
        # 如果后缀为空（纯 /command）或以非 ASCII 字母开头（中文等）/空格/标点，算匹配
        if not suffix or not (suffix[0].isascii() and suffix[0].isalnum()):
            return s["name"]
    return None


def parse_skill_params(skill_name: str, text: str) -> dict:
    pattern = _param_patterns.get(skill_name)
    if not pattern:
        return {}
    m = re.search(pattern, text)
    if not m or not m.lastindex:
        return {}
    param = m.group(1).strip()
    if skill_name == "memory":
        url_m = re.search(r"https?://[^\s]+", param)
        return {"url": url_m.group(0) if url_m else param}
    elif skill_name == "weather":
        return {"city": param}
    return {}


async def execute_skill(skill_name: str, params: dict, context: dict | None = None) -> str:
    handler = _handlers.get(skill_name)
    if not handler:
        return f"未知技能：{skill_name}"
    if context:
        params = {**params, **context}
    return await handler.execute(params, context)
