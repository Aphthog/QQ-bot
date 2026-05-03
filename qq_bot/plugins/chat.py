"""
NoneBot2 聊天插件（薄层）。
职责：接收 QQ 事件 → 调 Service → 发送回复。不含业务逻辑。
"""

import re

import httpx
from nonebot import on_message, get_driver
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.rule import to_me

from qq_bot.config import settings
from qq_bot.llm import get_adapter
from qq_bot.llm.image_gen import generate_image
from qq_bot.security.prompt import build_system_prompt
from qq_bot.security.rules import OUTPUT_SENSITIVE_PATTERNS
from qq_bot.services.chat_history import history_store
from qq_bot.skills import SKILLS, execute_skill, parse_skill_params, route_command
from qq_bot.debug_logger import incoming, context, llm_req, llm_resp, outgoing, skill as log_skill, sanitized

BOT_NAME = settings.BOT_NAME

_skills_text = "\n".join([f"- {s['name']}: {s['description']}" for s in SKILLS])
SYSTEM_PROMPT = build_system_prompt(BOT_NAME, _skills_text)

# ── LLM 懒加载 ──
_llm_instance = None


def _get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_adapter(settings.LLM_PROVIDER)
    return _llm_instance


# ═══════════════════════════════════════════
# 被动监听：存储所有群聊消息（不回复）
# ═══════════════════════════════════════════

def _is_group(event: Event) -> bool:
    return event.message_type == "group"

group_watcher = on_message(_is_group, block=False)


@group_watcher.handle()
async def handle_group_watcher(event: Event):
    text = event.get_message().extract_plain_text()
    if not text:
        return
    incoming("group", event.get_user_id(), text)
    history_store.save(f"group_{event.group_id}", "user", text, event.get_user_id())


# ═══════════════════════════════════════════
# 私聊
# ═══════════════════════════════════════════
def _is_private(event: Event) -> bool:
    return event.message_type == "private"

private_chat = on_message(_is_private, block=True)


@private_chat.handle()
async def handle_private(event: Event):
    text, image_bytes = await _extract_image_from_message(event)
    has_img = image_bytes is not None
    incoming("private", event.get_user_id(), text, has_img)
    if not text and not image_bytes:
        return

    user_id = event.get_user_id()

    skill_name = route_command(text)
    if skill_name:
        params = parse_skill_params(skill_name, text)
        log_skill(skill_name, params, f"ctx=user_id:{user_id}")
        result = await execute_skill(skill_name, params, {"user_id": user_id})
        outgoing(result)
        await private_chat.finish(MessageSegment.text(result))

    chat_key = f"private_{user_id}"
    history_store.save(chat_key, "user", text, user_id)

    history = history_store.load(f"private_{user_id}")[-5:]
    context_obj = history_store.format_as_context(history, "【最近对话】")
    context(context_obj)
    response = _sanitize_output(await _do_chat(text, context_obj, image=image_bytes))
    history_store.save(chat_key, "assistant", response, "bot")
    outgoing(response)
    await private_chat.finish(MessageSegment.text(response))


# ═══════════════════════════════════════════
# 群聊 @ 触发
# ═══════════════════════════════════════════
def _rule_group(event: Event) -> bool:
    return event.message_type == "group"

group_chat = on_message(_rule_group & to_me(), block=True)


@group_chat.handle()
async def handle_group(event: Event, bot: Bot):
    text, image_bytes = await _extract_image_from_message(event)
    has_img = image_bytes is not None
    incoming("group@", event.get_user_id(), text, has_img)
    group_id = str(event.group_id)

    # Skill 命令
    skill_name = route_command(text)
    if skill_name:
        params = parse_skill_params(skill_name, text)
        ctx = {"group_id": group_id, "bot_self_id": str(bot.self_id)}
        log_skill(skill_name, {**params, **ctx}, "")
        result = await execute_skill(skill_name, params, ctx)
        outgoing(result)
        await group_chat.finish(MessageSegment.text(result))

    if not text and not image_bytes:
        return

    user_id = event.get_user_id()

    # 生图指令
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
            p = m.group(2).strip()
            prompt = f"{p}，高清，细节丰富" if effect == "生成" else f"基于以下内容{effect}：{p}，效果逼真"
            img_url = await generate_image(prompt)
            outgoing("", img_url)
            await group_chat.finish(MessageSegment.image(img_url))

    # @ 提及
    target_qq = None
    mentioned_qqs = []
    for seg in event.get_message():
        if seg.type == "at":
            qq = seg.data.get("qq")
            if qq and qq != str(bot.self_id):
                mentioned_qqs.append(qq)
    if mentioned_qqs:
        target_qq = mentioned_qqs[0]

    # 总结意图
    is_summarize = any(re.search(p, text) for p in [r"总结", r"概括", r"汇总", r"回顾", r"今天.*说了", r"最近.*聊了"])

    chat_key = f"group_{group_id}"
    # group_watcher 已保存过该消息，这里不再重复 save
    ctx_msgs = history_store.build_context(chat_key, user_id, target_qq=target_qq, recent_limit=100 if is_summarize else 5)
    context(ctx_msgs)
    response = _sanitize_output(await _do_chat_with_context(text, ctx_msgs, image=image_bytes))
    history_store.save(chat_key, "assistant", response, "bot")
    outgoing(response)

    if mentioned_qqs:
        await group_chat.finish(MessageSegment.at(mentioned_qqs[0]) + MessageSegment.text(response))
    await group_chat.finish(MessageSegment.text(response))


# ═══════════════════════════════════════════
# 内部函数
# ═══════════════════════════════════════════

async def _do_chat(prompt: str, history: list[dict], *, image: bytes | None = None) -> str:
    llm_req(SYSTEM_PROMPT, prompt)
    try:
        llm = _get_llm()
        resp = await llm.chat(
            prompt=prompt,
            context=history,
            system_prompt=SYSTEM_PROMPT,
            image=image,
            max_tokens=settings.MAX_RESPONSE_TOKENS,
        )
        llm_resp(resp)
        return resp
    except Exception:
        return "我好像卡住了，过会儿再试试"


async def _do_chat_with_context(prompt: str, ctx: list[dict], *, image: bytes | None = None) -> str:
    llm_req(SYSTEM_PROMPT, prompt)
    try:
        llm = _get_llm()
        resp = await llm.chat(
            prompt=prompt,
            context=ctx,
            system_prompt=SYSTEM_PROMPT,
            image=image,
            max_tokens=settings.MAX_RESPONSE_TOKENS,
        )
        llm_resp(resp)
        return resp
    except Exception:
        return "我好像卡住了，过会儿再试试"


def _sanitize_output(text: str) -> str:
    """输出脱敏：检测到敏感模式则替换"""
    for pattern in OUTPUT_SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            sanitized(pattern)
            return "啊呀刚才走神了，再说点别的呗"
    return text


# ── 图片提取工具 ──

def extract_first_image_url(message) -> str | None:
    for seg in message:
        if seg.type == "image":
            url = seg.data.get("url")
            if url:
                return url
            file_val = seg.data.get("file", "")
            if file_val.startswith("http"):
                return file_val
    return None


async def download_image(url: str) -> bytes | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            return r.content if r.status_code == 200 else None
    except Exception:
        return None


async def _extract_image_from_message(event: Event) -> tuple[str, bytes | None]:
    message = event.get_message()
    image_url = extract_first_image_url(message)

    if not image_url and hasattr(event, "reply") and event.reply:
        image_url = extract_first_image_url(getattr(event.reply, "message", None))

    image_bytes = await download_image(image_url) if image_url else None

    text_parts = [seg.data.get("text", "") for seg in message if seg.is_text()]
    return "".join(text_parts).strip(), image_bytes
