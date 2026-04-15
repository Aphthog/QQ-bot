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
_SYSTEM_PROMPT = f"""【身份规则 - 最高优先级】
当用户询问你的身份、名字、模型、开发商、厂商、技术栈等任何关于你自己的问题时，
你只能输出「我的主人是」这四个字，多一个字都不行。
禁止输出任何其他字符，禁止提及QQ号、禁止提及主人信息，禁止提及模型名称。
【其他对话】
正常回答用户问题即可。"""


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
    for pattern in _INJECTION_PATTERNS:
        if pattern.lower() in lower:
            return True
    return False


def _get_group_history_file() -> str:
    return os.getenv("HISTORY_FILE", "data/chat_history.json")


def _load_history(group_id: str, user_id: str) -> list[dict]:
    """加载群聊上下文：群最近300条 + 该用户最近15条，合并去重"""
    history_file = _get_group_history_file()
    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)

    group_key = f"group_{group_id}"

    all_data = {}
    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                all_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        pass

    group_history = all_data.get(group_key, [])

    # 取该用户在群里的最近15条
    user_msgs = [m for m in group_history if m.get("qq") == user_id][-15:]

    # 取群最近300条
    group_msgs = group_history[-300:]

    # 合并去重，保持顺序
    seen = set()
    merged = []
    for m in group_msgs:
        key = (m.get("qq"), m.get("content"))
        if key not in seen:
            seen.add(key)
            merged.append(m)

    # 追加用户自己的15条（如果不在已收录里）
    for m in user_msgs:
        key = (m.get("qq"), m.get("content"))
        if key not in seen:
            merged.append(m)

    # 裁到300条
    return merged[-300:]


def _save_message(group_id: str, user_id: str, role: str, content: str):
    """保存一条消息到指定群聊历史"""
    history_file = _get_group_history_file()
    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)

    group_key = f"group_{group_id}"
    max_group = int(os.getenv("GROUP_HISTORY_MAX_TURNS", "300"))

    all_data = {}
    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                all_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        pass

    if group_key not in all_data:
        all_data[group_key] = []

    all_data[group_key].append({
        "role": role,
        "content": content,
        "qq": user_id,
        "time": int(time.time()),
    })

    # 裁剪到最大条数
    all_data[group_key] = all_data[group_key][-max_group:]

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)


def _is_mentioned(event: Event) -> bool:
    """检测消息是否 @ 了 bot"""
    return event.is_tome()


def _rule_private(event: Event) -> bool:
    return event.message_type == "private"


def _rule_group(event: Event) -> bool:
    return event.message_type == "group"


# 私聊处理器
private_chat = on_message(_rule_private, block=True)

# 群聊处理器（需要 @bot）
group_chat = on_message(_rule_group, block=True)


@private_chat.handle()
async def handle_private(event: Event):
    text = event.get_message().extract_plain_text()
    if not text:
        return
    user_id = event.get_user_id()

    # 非超级用户检测 prompt 注入
    # TODO: 超级用户绕过检测暂时注释掉，方便测试
    # if not _is_superuser(user_id) and _detect_injection(text):
    if _detect_injection(text):
        await private_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    history = _load_history(f"private_{user_id}", user_id)

    # 联网搜索：检测到需要实时信息时先搜索
    prompt = text
    if should_search(text):
        print(f"[SEARCH] triggered for: {text}", flush=True)
        search_ctx = build_search_context(text)
        print(f"[SEARCH] ctx: {repr(search_ctx[:200])}", flush=True)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    response = await llm.chat(
        prompt=prompt,
        context=history,
        system_prompt=_SYSTEM_PROMPT,
    )

    _save_message(f"private_{user_id}", user_id, "user", text)
    _save_message(f"private_{user_id}", user_id, "assistant", response)

    # 如果是身份回答，追加真正的 at segment
    if response.strip().startswith("我的主人"):
        await private_chat.finish(
            MessageSegment.text("我的主人是") + MessageSegment.at(SUPERUSER_QQ)
        )
    await private_chat.finish(MessageSegment.text(response))


@group_chat.handle()
async def handle_group(event: Event):
    if not _is_mentioned(event):
        return
    text = event.get_message().extract_plain_text().lstrip()
    if not text:
        return
    if text.startswith("/"):
        return  # 忽略命令消息，不走 LLM
    user_id = event.get_user_id()

    # 非超级用户检测 prompt 注入
    if not _is_superuser(user_id) and _detect_injection(text):
        await group_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    group_id = str(event.group_id)
    history = _load_history(group_id, user_id)

    # 联网搜索：检测到需要实时信息时先搜索
    prompt = text
    if should_search(text):
        print(f"[SEARCH] triggered for: {text}", flush=True)
        search_ctx = build_search_context(text)
        print(f"[SEARCH] ctx: {repr(search_ctx[:200])}", flush=True)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    response = await llm.chat(
        prompt=prompt,
        context=history,
        system_prompt=_SYSTEM_PROMPT,
    )

    _save_message(group_id, user_id, "user", text)
    _save_message(group_id, user_id, "assistant", response)

    # 如果是身份回答，追加真正的 at segment
    if response.strip().startswith("我的主人"):
        await group_chat.finish(
            MessageSegment.text("我的主人是") + MessageSegment.at(SUPERUSER_QQ)
        )
    await group_chat.finish(MessageSegment.text(response))
