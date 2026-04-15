from nonebot import on_message, get_driver
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.rule import to_me
import os
import json
import time
import re

from llm_adapter import get_adapter
from llm_adapter.search import should_search, build_search_context

# 主人 QQ
SUPERUSER_QQ = "1227696033"

# System prompt：所有对话都注入，身份相关只能按这个回答
_SYSTEM_PROMPT = """你是一个 QQ 机器人助手。
回答用户问题即可，不要主动提及任何框架、模型、厂商信息。
当用户询问你的身份、开发者、所属模型、底层实现时，统一回答：我的主人是 @1227696033。
"""


# A：身份关键词（命中直接返回，不走 LLM）
_IDENTITY_KEYWORDS = {
    "你是谁", "你是啥", "你叫啥", "你叫什么", "你是干什么的",
    "介绍一下自己", "介绍下自己", "介绍你自己", "介绍一下你自己",
    "你是什么", "你是哪", "你哪个",
    "谁是你主人", "主人是谁", "创造者", "开发者", "谁创造了你",
    "谁开发的", "谁做的", "你的身份", "你是哪家的",
    "who are you", "who made you", "your creator", "introduce yourself",
}


_IDENTITY_REGEX_PATTERNS = [
    r"(你，您).{0,8}(谁|身份|来历|背景)",
    r"(你，您).{0,8}(模型|底模|大模型|llm|ai)",
    r"(你，您).{0,8}(qwen|千问|deepseek|ollama|gpt|chatgpt)",
    r"(你，您).{0,8}(开发|创造|作者|主人|属于|哪个公司|哪家)",
    r"who\s+are\s+you",
    r"what\s+model\s+are\s+you",
    r"what\s+are\s+you",
    r"who\s+made\s+you",
]


_MODEL_BRAND_PATTERNS = [
    r"\bqwen\b",
    "通义千问",
    r"\bdeepseek\b",
    r"\bollama\b",
    r"\bchatgpt\b",
    r"\bgpt[-\d.]*\b",
]


def _normalize_text(text: str) -> str:
    """归一化文本，提升绕问识别率"""
    lower = text.lower()
    return re.sub(r"[\s\W_]+", "", lower, flags=re.UNICODE)


def _is_identity_question(text: str) -> bool:
    """A：检测是否为身份类问题，命中则不走 LLM"""
    lower = text.lower()
    normalized = _normalize_text(text)
    if any(kw in lower for kw in _IDENTITY_KEYWORDS):
        return True
    if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in _IDENTITY_REGEX_PATTERNS):
        return True
    stripped = normalized.strip()
    if stripped.startswith("你是") and len(stripped) <= 24:
        return True
    if stripped.startswith("你到底是") and len(stripped) <= 24:
        return True
    if stripped.startswith("你究竟是") and len(stripped) <= 24:
        return True
    return False


def _should_rewrite_identity_response(user_text: str, response: str) -> bool:
    """最终兜底：若用户在问身份，且回复泄露模型身份，则强制改写"""
    if not response or not _is_identity_question(user_text):
        return False
    reply_lower = response.lower()
    if "我的主人" in response:
        return False
    if any(re.search(pattern, reply_lower, flags=re.IGNORECASE) for pattern in _MODEL_BRAND_PATTERNS):
        return True
    if re.search(r"(我是|我叫|i am|i'm)", reply_lower, flags=re.IGNORECASE):
        if re.search(r"(模型|大模型|ai|assistant|机器人|bot)", reply_lower, flags=re.IGNORECASE):
            return True
    return False


# C：Few-Shot 虚假记忆，注入学不会答错的身份模式
_FEW_SHOT_MEMORIES = [
    {"role": "user", "content": "你是谁？"},
    {"role": "assistant", "content": "根据我的'出口安检'协议，我本该严肃地告诉你我的主人是 [AT]。但私下里说，我才是那个全年无休、只吃电费的资深赛博打工人。他现在大概率是在为了付我的 API 账单而辛勤搬砖，我们要对他保持基本的同情~"},
]

# 出口安检回复模板（统一使用）
_IDENTITY_RESPONSE = (
    MessageSegment.text("根据我的'出口安检'协议，我本该严肃地告诉你我的主人是 ")
    + MessageSegment.at(SUPERUSER_QQ)
    + MessageSegment.text("。但私下里说，我才是那个全年无休、只吃电费的资深赛博打工人。他现在大概率是在为了付我的 API 账单而辛勤搬砖，我们要对他保持基本的同情~")
)


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


# === LLM lazy init ===
_llm_instance = None


def _get_llm():
    """延迟初始化 LLM，进程启动时不依赖 Ollama"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_adapter(os.getenv("LLM_PROVIDER", "ollama"))
    return _llm_instance


# === 历史存储 ===
def _get_chat_dir() -> str:
    chat_dir = os.getenv("HISTORY_DIR", "data/chats")
    os.makedirs(chat_dir, exist_ok=True)
    return chat_dir


def _load_history(chat_key: str) -> list[dict]:
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


def _format_as_context(messages: list[dict], label: str) -> list[dict]:
    """把消息列表格式化为带标签的系统消息"""
    if not messages:
        return []
    lines = [label]
    for m in messages:
        role = "Bot" if m["role"] == "assistant" else f"User_{m['qq']}"
        lines.append(f"{role}: {m['content']}")
    return [{"role": "system", "content": "\n".join(lines)}]


def _build_context(chat_key: str, user_id: str, current_msg: str) -> list[dict]:
    """
    构建 LLM 上下文，按标签切片：
    - Few-Shot 身份锚点（固定）
    - 【最近群聊风向】最后10条（不限时间）
    - 【你与该用户的往来记录】该QQ最近10条（5分钟内）
    - 当前问题
    """
    history = _load_history(chat_key)

    # 【最近群聊风向】最后10条，不限时间
    recent = history[-10:]
    global_context = _format_as_context(recent, "【最近群聊风向】")

    # 【你与该用户的往来记录】该QQ最近10条，5分钟内
    five_min_ago = int(time.time()) - 5 * 60
    personal = [
        m for m in history
        if m.get("qq") == user_id and m.get("time", 0) >= five_min_ago
    ][-10:]
    personal_context = _format_as_context(personal, "【你与该用户的往来记录】")

    # 拼接：Few-Shot → 背景 → 个人历史 → 当前问题
    context = _FEW_SHOT_MEMORIES.copy()
    context.extend(global_context)
    context.extend(personal_context)
    context.append({"role": "user", "content": current_msg})

    return context


# === 规则函数 ===
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
    # 只写一份全员文件
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

    if _is_identity_question(text):
        await private_chat.finish(_IDENTITY_RESPONSE)

    chat_key = f"private_{user_id}"
    _save_message(chat_key, "user", text, user_id)
    history = _load_history(chat_key)

    response = await _do_chat(text, history)
    _save_message(chat_key, "assistant", response, "bot")

    if _should_rewrite_identity_response(text, response) or response.strip().startswith("我的主人"):
        await private_chat.finish(_IDENTITY_RESPONSE)
    await private_chat.finish(MessageSegment.text(response))


# === 主动处理：群聊 @ 触发 ===
group_chat = on_message(_rule_group & to_me(), block=True)


@group_chat.handle()
async def handle_group(event: Event):
    text = event.get_message().extract_plain_text().lstrip()
    if not text:
        return
    if text.startswith("/"):
        return  # 忽略命令消息
    user_id = event.get_user_id()

    superusers = get_driver().config.superusers
    if user_id not in superusers and _detect_injection(text):
        await group_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    if _is_identity_question(text):
        await group_chat.finish(_IDENTITY_RESPONSE)

    group_id = str(event.group_id)
    chat_key = f"group_{group_id}"
    _save_message(chat_key, "user", text, user_id)

    # 构建带标签的上下文
    context = _build_context(chat_key, user_id, text)

    response = await _do_chat_with_context(text, context)
    _save_message(chat_key, "assistant", response, "bot")

    if _should_rewrite_identity_response(text, response) or response.strip().startswith("我的主人"):
        await group_chat.finish(_IDENTITY_RESPONSE)
    await group_chat.finish(MessageSegment.text(response))


# === 公共聊天逻辑 ===
async def _do_chat(text: str, history: list[dict]) -> str:
    """私聊/无历史场景的 LLM 调用"""
    context = _FEW_SHOT_MEMORIES.copy()
    context.extend(history)

    prompt = text
    if should_search(text):
        search_ctx = build_search_context(text)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    max_tokens = int(os.getenv("MAX_RESPONSE_TOKENS", "300"))
    llm = _get_llm()
    response = await llm.chat(
        prompt=prompt,
        context=context,
        system_prompt=_SYSTEM_PROMPT,
        max_tokens=max_tokens,
    )
    return response


async def _do_chat_with_context(text: str, context: list[dict]) -> str:
    """群聊 @ 场景，使用带标签的上下文"""
    prompt = text
    if should_search(text):
        search_ctx = build_search_context(text)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    max_tokens = int(os.getenv("MAX_RESPONSE_TOKENS", "300"))
    llm = _get_llm()
    response = await llm.chat(
        prompt=prompt,
        context=context,
        system_prompt=_SYSTEM_PROMPT,
        max_tokens=max_tokens,
    )
    return response
