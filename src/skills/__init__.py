"""
Skill System - 技能系统
SKILLS 定义 + 路由 + 执行
"""

from .handlers.memory import MemorySkill
from .handlers.weather import WeatherSkill
from .handlers.group_stats import GroupStatsSkill
from .handlers.random_mention import RandomMentionSkill
import re

# Skill 描述列表（暴露给 LLM）
SKILLS = [
    {
        "name": "memory",
        "description": "将网页URL内容存入知识库，供后续检索使用。格式：/memory <网址>",
    },
    {
        "name": "weather",
        "description": "查询城市天气情况。格式：/weather <城市>",
    },
    {
        "name": "top",
        "description": "查看群聊发言排行榜，显示Top5发言最多的群友。格式：/top",
    },
    {
        "name": "random",
        "description": "从群聊最近活跃用户中随机艾特一人。格式：/random",
    },
]

# Skill 类映射（用于执行）
SKILL_HANDLERS = {
    "memory": MemorySkill(),
    "weather": WeatherSkill(),
    "top": GroupStatsSkill(),
    "random": RandomMentionSkill(),
}

# Skill 参数解析规则（从命令文本提取参数）
SKILL_PARAM_PATTERNS = {
    "memory": r'/memory\s+(.+)',
    "weather": r'/weather\s+(.+)',
    "top": r'/top',
    "random": r'/random',
}


def route_command(text: str) -> str | None:
    """根据命令文本匹配 skill，返回 skill name"""
    text = text.strip()
    for skill in SKILLS:
        name = skill["name"]
        if text.startswith(f"/{name}"):
            return name
    return None


def parse_skill_params(skill_name: str, text: str) -> dict:
    """从命令文本解析 skill 参数"""
    pattern = SKILL_PARAM_PATTERNS.get(skill_name)
    if not pattern:
        return {}
    match = re.search(pattern, text)
    if not match:
        return {}

    param = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""

    # 不同 skill 返回不同参数
    if skill_name == "memory":
        # 提取 URL
        url_match = re.search(r'https?://[^\s]+', param)
        return {"url": url_match.group(0) if url_match else param}
    elif skill_name == "weather":
        return {"city": param}
    elif skill_name in ("top", "random"):
        # 这些 skill 需要群组 ID 和机器人 ID，从事件上下文获取
        return {}

    return {}


def route_tool_call(tool_calls: list) -> tuple[str, dict] | None:
    """解析 LLM 返回的 tool_calls，返回 (skill_name, arguments)"""
    if not tool_calls:
        return None
    # 只处理第一个 tool_call
    tc = tool_calls[0]
    func = tc.get("function", {})
    name = func.get("name")
    arguments = func.get("arguments", {})
    # arguments 可能是 str（JSON string）或 dict
    if isinstance(arguments, str):
        import json
        arguments = json.loads(arguments)
    return name, arguments


async def execute_skill(skill_name: str, params: dict, context: dict | None = None) -> str:
    """执行 skill，返回结果字符串"""
    handler = SKILL_HANDLERS.get(skill_name)
    if not handler:
        return f"未知技能：{skill_name}"

    # 注入上下文（group_id, bot_self_id 等）
    if context:
        params = {**params, **context}

    return await handler.execute(params)