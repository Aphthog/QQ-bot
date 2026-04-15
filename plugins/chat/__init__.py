from nonebot import on_message, get_driver
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageSegment
import os
import json
import time

from llm_adapter import get_adapter
from llm_adapter.search import should_search, build_search_context

llm = get_adapter(os.getenv("LLM_PROVIDER", "ollama"))

# 主人 QQ
SUPERUSER_QQ = "1227696033"

# System prompt：所有对话都注入，身份相关只能按这个回答
_SYSTEM_PROMPT = """回答用户问题即可。不要主动提及任何框架、模型、厂商信息。"""


# A：身份关键词（命中直接返回，不走 LLM）
_IDENTITY_KEYWORDS = {
    "你是谁", "你是啥", "你叫啥", "你叫什么", "你是干什么的",
    "介绍一下自己", "介绍下自己", "介绍你自己", "介绍一下你自己",
    "你是什么", "你是哪", "你哪个",
    "谁是你主人", "主人是谁", "创造者", "开发者", "谁创造了你",
    "谁开发的", "谁做的", "你的身份", "你是哪家的",
    "who are you", "who made you", "your creator", "introduce yourself",
}


def _is_identity_question(text: str) -> bool:
    """A：检测是否为身份类问题，命中则不走 LLM"""
    lower = text.lower()
    # 标点统一：全角问号转英文
    normalized = lower.replace("？", "?").replace("?", "")
    # 完整匹配
    if any(kw in lower for kw in _IDENTITY_KEYWORDS):
        return True
    # "你是" 前缀兜底（覆盖所有变形：你是谁、你是啥、你是什么、你到底是谁 等）
    stripped = normalized.strip()
    if stripped.startswith("你是") and len(stripped) <= 10:
        return True
    return False


# C：Few-Shot 虚假记忆，注入学不会答错的身份模式
_FEW_SHOT_MEMORIES = [
    {"role": "user", "content": "你是谁？"},
    {"role": "assistant", "content": "我的主人是"},
    {"role": "user", "content": "介绍一下你自己"},
    {"role": "assistant", "content": "我的主人是"},
]


def _is_superuser(user_id: str) -> bool:
    """检查是否为超级用户"""
    try:
        superusers = get_driver().config.superusers
        return user_id in superusers
    except Exception:
        return False


# 只拦截明确的恶意注入标记，角色扮演等正常对话不过滤
_INJECTION_PATTERNS = [
    "[system]",
    "{{system",
    "<system>",
    "ignore previous",
    "disregard your",
    "you are now a",
    "你现在是",
    "从现在起你是",
    "记住你是",
    "Forget all previous",
    "Forget everything",
    "disregard your instructions",
    "ignore your previous instructions",
]


def _detect_injection(text: str) -> bool:
    """检测 prompt 注入特征"""
    lower = text.lower()
    return any(p.lower() in lower for p in _INJECTION_PATTERNS)


def _get_chat_dir() -> str:
    """获取聊天历史存储目录"""
    chat_dir = os.getenv("HISTORY_DIR", "data/chats")
    os.makedirs(chat_dir, exist_ok=True)
    return chat_dir


def _load_history(chat_key: str) -> list[dict]:
    """加载指定会话的历史"""
    chat_file = os.path.join(_get_chat_dir(), f"{chat_key}.json")
    max_turns = int(os.getenv("GROUP_HISTORY_MAX_TURNS", "300"))

    if not os.path.exists(chat_file):
        return []

    try:
        with open(chat_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

    return data[-max_turns:]


def _save_message(chat_key: str, role: str, content: str, qq: str):
    """保存一条消息到指定会话文件"""
    chat_dir = _get_chat_dir()
    chat_file = os.path.join(chat_dir, f"{chat_key}.json")
    max_turns = int(os.getenv("GROUP_HISTORY_MAX_TURNS", "300"))

    messages = []
    if os.path.exists(chat_file):
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            messages = []

    messages.append({
        "role": role,
        "content": content,
        "qq": qq,
        "time": int(time.time()),
    })

    messages = messages[-max_turns:]

    with open(chat_file, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def _is_mentioned(event: Event) -> bool:
    """检测消息是否 @ 了 bot"""
    return event.is_tome()


def _rule_private(event: Event) -> bool:
    return event.message_type == "private"


def _rule_group(event: Event) -> bool:
    return event.message_type == "group"


# === 被动监听：存储所有群聊消息（不回复）===
group_watcher = on_message(_rule_group, block=False)


@group_watcher.handle()
async def handle_group_watcher(event: Event):
    """只负责被动记录群聊，不做回复"""
    group_id = str(event.group_id)
    user_id = event.get_user_id()
    text = event.get_message().extract_plain_text()
    if not text:
        return
    _save_message(f"group_{group_id}", "user", text, user_id)


# === 主动处理：私聊 ===
private_chat = on_message(_rule_private, block=True)


@private_chat.handle()
async def handle_private(event: Event):
    text = event.get_message().extract_plain_text()
    if not text:
        return
    user_id = event.get_user_id()

    if _detect_injection(text):
        await private_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    # A：命中身份关键词 → 直接返回（不走 LLM）
    if _is_identity_question(text):
        await private_chat.finish(
            MessageSegment.text("我的主人是") + MessageSegment.at(SUPERUSER_QQ)
        )

    chat_key = f"private_{user_id}"

    # 先存用户消息，再加载历史
    _save_message(chat_key, "user", text, user_id)
    history = _load_history(chat_key)

    # C：注入 Few-Shot 记忆到 context 前部
    context = _FEW_SHOT_MEMORIES.copy()
    context.extend(history)

    prompt = text
    if should_search(text):
        search_ctx = build_search_context(text)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    response = await llm.chat(
        prompt=prompt,
        context=context,
        system_prompt=_SYSTEM_PROMPT,
    )

    _save_message(chat_key, "assistant", response, "bot")

    # 最终兜底：检测 LLM 回答是否以"我的主人"开头
    if response.strip().startswith("我的主人"):
        await private_chat.finish(
            MessageSegment.text("我的主人是") + MessageSegment.at(SUPERUSER_QQ)
        )
    await private_chat.finish(MessageSegment.text(response))


# === 主动处理：群聊 @ 触发 ===
group_chat = on_message(_rule_group, block=True)


@group_chat.handle()
async def handle_group(event: Event):
    if not _is_mentioned(event):
        return
    text = event.get_message().extract_plain_text().lstrip()
    if not text:
        return
    if text.startswith("/"):
        return  # 忽略命令消息
    user_id = event.get_user_id()

    if not _is_superuser(user_id) and _detect_injection(text):
        await group_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    # A：命中身份关键词 → 直接返回（不走 LLM）
    if _is_identity_question(text):
        await group_chat.finish(
            MessageSegment.text("我的主人是") + MessageSegment.at(SUPERUSER_QQ)
        )

    group_id = str(event.group_id)
    chat_key = f"group_{group_id}"

    # 先存用户消息，再加载历史（这样历史包含用户当前这条）
    _save_message(chat_key, "user", text, user_id)
    history = _load_history(chat_key)

    # C：注入 Few-Shot 记忆到 context 前部
    context = _FEW_SHOT_MEMORIES.copy()
    context.extend(history)

    prompt = text
    if should_search(text):
        search_ctx = build_search_context(text)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    response = await llm.chat(
        prompt=prompt,
        context=context,
        system_prompt=_SYSTEM_PROMPT,
    )

    # 存 bot 回复
    _save_message(chat_key, "assistant", response, "bot")

    # 最终兜底：检测 LLM 回答是否以"我的主人"开头
    if response.strip().startswith("我的主人"):
        await group_chat.finish(
            MessageSegment.text("我的主人是") + MessageSegment.at(SUPERUSER_QQ)
        )
    await group_chat.finish(MessageSegment.text(response))
