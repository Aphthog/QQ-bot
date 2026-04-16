from nonebot import on_message, get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.rule import to_me
import os
import json
import time
import re
import httpx

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


# C：Few-Shot 虚假记忆已移除（龙猫 API 不接受 assistant 历史消息）

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
    """把消息列表格式化为带标签的系统消息（龙猫格式：content 必须是列表）"""
    if not messages:
        return []
    lines = [label]
    for m in messages:
        role = "Bot" if m["role"] == "assistant" else f"User_{m['qq']}"
        lines.append(f"{role}: {m['content']}")
    return [{"role": "system", "content": [{"type": "text", "text": "\n".join(lines)}]}]


def _build_context(chat_key: str, user_id: str, target_qq: str | None = None, recent_limit: int = 5) -> list[dict]:
    """
    构建 LLM 上下文，按标签切片：
    - 【最近群聊风向】最近N条（默认5条，总结时20条）
    - 【你与该用户的往来记录】该QQ最近5条（5分钟内）
    - 【目标用户消息】（如有指定）目标用户在群中的最近5条
    注意：龙猫 API 不接受 assistant 历史消息，所以 context 只包含 system 消息。
    当前问题通过 llm.chat 的 prompt 参数单独传递。
    """
    history = _load_history(chat_key)

    # 【最近群聊风向】最近N条
    recent = history[-recent_limit:]
    global_context = _format_as_context(recent, "【最近群聊风向】")

    # 【你与该用户的往来记录】该QQ最近5条，5分钟内
    five_min_ago = int(time.time()) - 5 * 60
    personal = [
        m for m in history
        if m.get("qq") == user_id and m.get("time", 0) >= five_min_ago
    ][-5:]
    personal_context = _format_as_context(personal, "【你与该用户的往来记录】")

    # 【目标用户消息】如果用户指定了点评对象
    target_context = []
    if target_qq:
        target_msgs = [m for m in history if m.get("qq") == target_qq][-5:]
        if target_msgs:
            target_context = _format_as_context(target_msgs, f"【{target_qq}的发言】")

    # 拼接：背景 → 个人历史 → 目标用户（当前问题通过 prompt 参数单独传递）
    context = []
    context.extend(global_context)
    context.extend(personal_context)
    context.extend(target_context)

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
    message = event.get_message()
    text, image_bytes = await _extract_image_from_message(message)
    if not text and not image_bytes:
        return
    user_id = event.get_user_id()

    if _detect_injection(text):
        await private_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    if _is_identity_question(text):
        await private_chat.finish(_IDENTITY_RESPONSE)

    # 检查生图指令
    image_gen_patterns = [
        (r"^(画|生成|创作|给我画|帮我画)\s*(.+)", "生成"),
        (r"^(反转|翻转|倒转)\s*(.+)", "水平翻转"),
        (r"^(左右对称|镜像)\s*(.+)", "左右对称"),
        (r"^(上下对称)\s*(.+)", "上下对称"),
        (r"^(旋转|转一转)\s*(.+)", "旋转"),
        (r"^(彩色|上色)\s*(.+)", "彩色化"),
    ]
    for pattern, effect in image_gen_patterns:
        m = re.match(pattern, text)
        if m:
            prompt = m.group(2).strip()
            if effect == "生成":
                prompt = f"{prompt}，高清，细节丰富"
            else:
                prompt = f"基于以下内容{effect}：{prompt}，效果逼真"
            from llm_adapter.pollinations import generate_image
            img_url = await generate_image(prompt)
            await private_chat.finish(MessageSegment.image(img_url))

    chat_key = f"private_{user_id}"
    _save_message(chat_key, "user", text, user_id)
    history = _load_history(chat_key)

    response = await _do_chat(text, history, image=image_bytes)
    _save_message(chat_key, "assistant", response, "bot")

    if _should_rewrite_identity_response(text, response) or response.strip().startswith("我的主人"):
        await private_chat.finish(_IDENTITY_RESPONSE)
    await private_chat.finish(MessageSegment.text(response))


# === 主动处理：群聊 @ 触发 ===
group_chat = on_message(_rule_group & to_me(), block=True)


@group_chat.handle()
async def handle_group(event: Event, bot: Bot):
    message = event.get_message()
    text, image_bytes = await _extract_image_from_message(message)

    # 如果当前消息没图片，检查引用消息中的图片
    if not image_bytes:
        reply = getattr(event, "reply", None)
        if reply:
            # reply.message 是 MessageSegment 对象列表
            reply_msg = getattr(reply, "message", None)
            if reply_msg:
                for seg in reply_msg:
                    if seg.type == "image":
                        img_url = seg.data.get("url")
                        if img_url:
                            try:
                                async with httpx.AsyncClient(timeout=30.0) as client:
                                    r = await client.get(img_url)
                                    if r.status_code == 200:
                                        image_bytes = r.content
                            except Exception:
                                pass
                            break

    text = text.lstrip()
    if not text and not image_bytes:
        return
    if text.startswith("/"):
        return  # 忽略命令消息
    user_id = event.get_user_id()
    group_id = str(event.group_id)

    superusers = get_driver().config.superusers
    if user_id not in superusers and _detect_injection(text):
        await group_chat.finish(MessageSegment.text("检测到异常指令，已拒绝执行。"))

    if _is_identity_question(text):
        await group_chat.finish(_IDENTITY_RESPONSE)

    # 检查生图指令
    image_gen_patterns = [
        (r"^(画|生成|创作|给我画|帮我画)\s*(.+)", "生成"),
        (r"^(反转|翻转|倒转)\s*(.+)", "水平翻转"),
        (r"^(左右对称|镜像)\s*(.+)", "左右对称"),
        (r"^(上下对称)\s*(.+)", "上下对称"),
        (r"^(旋转|转一转)\s*(.+)", "旋转"),
        (r"^(彩色|上色)\s*(.+)", "彩色化"),
    ]
    for pattern, effect in image_gen_patterns:
        m = re.match(pattern, text)
        if m:
            prompt = m.group(2).strip()
            if effect == "生成":
                prompt = f"{prompt}，高清，细节丰富"
            else:
                prompt = f"基于以下内容{effect}：{prompt}，效果逼真"
            from llm_adapter.pollinations import generate_image
            img_url = await generate_image(prompt)
            await group_chat.finish(MessageSegment.image(img_url))

    # 提取消息中的 @ 提及，找到被提及的用户QQ
    target_qq = None
    mentioned_qqs = []
    for seg in message:
        if seg.type == "at":
            qq = seg.data.get("qq")
            if qq and qq != str(bot.self_id):
                mentioned_qqs.append(qq)
    # 优先用第一个被提及的用户（点评对象）
    if mentioned_qqs:
        target_qq = mentioned_qqs[0]

    # 检测总结/概括意图，用更多历史消息
    summarize_patterns = [r"总结", r"概括", r"汇总", r"回顾", r"今天.*说了", r"最近.*聊了"]
    is_summarize = any(re.search(p, text) for p in summarize_patterns)
    recent_limit = 20 if is_summarize else 5

    # 检测随机艾特指令（需要 group_id）
    if re.search(r"随机.*艾特|随便.*@|抽一个", text):
        import random
        candidates = None
        try:
            members = await bot.call_api("get_group_member_list", group_id=int(group_id))
            candidates = [m for m in members if str(m["user_id"]) != user_id and str(m["user_id"]) != str(bot.self_id)]
        except Exception:
            pass

        if candidates:
            chosen = random.choice(candidates)
            chosen_qq = str(chosen["user_id"])
            await group_chat.finish(MessageSegment.at(chosen_qq))
        else:
            await group_chat.finish(MessageSegment.text("随机艾特失败了..."))

    chat_key = f"group_{group_id}"
    _save_message(chat_key, "user", text, user_id)

    # 构建带标签的上下文（传入目标用户和历史条数）
    context = _build_context(chat_key, user_id, target_qq=target_qq, recent_limit=recent_limit)

    response = await _do_chat_with_context(text, context, image=image_bytes)
    _save_message(chat_key, "assistant", response, "bot")

    if _should_rewrite_identity_response(text, response) or response.strip().startswith("我的主人"):
        await group_chat.finish(_IDENTITY_RESPONSE)

    # 如果消息中 @ 了别人，回复时也 @ 对方（用名字显示）
    if mentioned_qqs:
        await group_chat.finish(MessageSegment.at(mentioned_qqs[0]) + MessageSegment.text(response))
    await group_chat.finish(MessageSegment.text(response))


# === 图片提取 ===
async def _extract_image_from_message(message) -> tuple[str, bytes | None]:
    """从消息中提取图片和纯文本，返回 (纯文本, 图片字节)"""
    import httpx
    image_bytes = None
    text_parts = []
    for seg in message:
        if seg.type == "image":
            # 优先取 url，其次取 file（可能是 url 或 base64）
            url = seg.data.get("url")
            if not url:
                file_val = seg.data.get("file", "")
                if file_val.startswith("http"):
                    url = file_val
                elif file_val.startswith("base64://"):
                    import base64
                    image_bytes = base64.b64decode(file_val[9:])
            if url and image_bytes is None:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.get(url)
                    image_bytes = r.content
        elif seg.is_text():
            txt = seg.data.get("text", "")
            if txt:
                text_parts.append(txt)
    return "".join(text_parts).strip(), image_bytes


# === 公共聊天逻辑 ===
async def _do_chat(text: str, history: list[dict], *, image: bytes | None = None) -> str:
    """私聊/无历史场景的 LLM 调用"""
    # 龙猫 API 不接受 assistant 历史消息，把历史汇总到用户消息里
    if not history:
        summary = ""
    else:
        recent = history[-6:]
        lines = []
        for m in recent:
            role = "用户" if m["role"] == "user" else "助手"
            lines.append(f"{role}：{m['content']}")
        summary = "\n".join(lines)
    if summary:
        prompt = f"【对话历史】\n{summary}\n\n【当前】{text}"
    else:
        prompt = text

    if should_search(text):
        search_ctx = build_search_context(text)
        if search_ctx:
            prompt = f"{search_ctx}\n\n{prompt}"

    max_tokens = int(os.getenv("MAX_RESPONSE_TOKENS", "300"))
    llm = _get_llm()
    response = await llm.chat(
        prompt=prompt,
        context=[],
        system_prompt=_SYSTEM_PROMPT,
        image=image,
        max_tokens=max_tokens,
    )
    return response


async def _do_chat_with_context(text: str, context: list[dict], *, image: bytes | None = None) -> str:
    """群聊 @ 场景，使用带标签的上下文"""
    # 龙猫 API 不接受 assistant 历史消息，过滤掉
    clean_context = [m for m in context if m.get("role") != "assistant"]
    prompt = text
    if should_search(text):
        search_ctx = build_search_context(text)
        if search_ctx:
            prompt = f"{search_ctx}\n\n用户问题：{text}"

    max_tokens = int(os.getenv("MAX_RESPONSE_TOKENS", "300"))
    llm = _get_llm()
    response = await llm.chat(
        prompt=prompt,
        context=clean_context,
        system_prompt=_SYSTEM_PROMPT,
        image=image,
        max_tokens=max_tokens,
    )
    return response
