"""Chat plugin: connects NoneBot2 events to the AgentLoop."""
from __future__ import annotations

import time
import logging

import httpx
from nonebot import on_message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.rule import to_me

from qq_bot.config import config
from qq_bot.agent.core import AgentLoop
from qq_bot.llm.gateway import LLMGateway
from qq_bot.memory.manager import MemoryManager
from qq_bot.access.guard import AccessGuard

logger = logging.getLogger("qq_bot.plugins.chat")

# Last bot reply timestamp per (chat_key, user_id) for session carry-over
_last_reply: dict[str, float] = {}

# Global singletons (initialized in bot.py)
agent: AgentLoop | None = None
memory: MemoryManager | None = None
guard: AccessGuard | None = None


def _get_chat_key(event: Event) -> str:
    if event.message_type == "group":
        return f"group_{getattr(event, 'group_id', '')}"
    return f"private_{event.get_user_id()}"


def _check_trigger(event: Event) -> str | None:
    """Return user_id if this message should trigger the bot, None otherwise."""
    user_id = event.get_user_id()

    # Private chat always triggers
    if event.message_type == "private":
        return user_id

    # @bot triggers
    if to_me()(event).call(None):
        return user_id

    # Session carry-over: reply within window
    chat_key = _get_chat_key(event)
    window_key = f"{chat_key}:{user_id}"
    if window_key in _last_reply:
        if time.time() - _last_reply[window_key] < config.SESSION_CARRY_WINDOW:
            return user_id

    return None


def _extract_text_and_images(event: Event) -> tuple[str, list[str]]:
    """Extract text and image URLs from an event."""
    text_parts: list[str] = []
    image_urls: list[str] = []
    for seg in event.get_message():
        if seg.type == "text":
            text_parts.append(seg.data.get("text", ""))
        elif seg.type == "image":
            url = seg.data.get("url", "")
            if url:
                image_urls.append(url)
    return "".join(text_parts).strip(), image_urls


def _extract_text_and_images_from_msg(msg: dict) -> tuple[str, list[str]]:
    """Extract text and image URLs from a quoted message dict (from bot.get_msg)."""
    text_parts: list[str] = []
    image_urls: list[str] = []
    for seg in msg.get("message", []):
        seg_type = seg.get("type", "")
        if seg_type == "text":
            text_parts.append(seg.get("data", {}).get("text", ""))
        elif seg_type == "image":
            url = seg.get("data", {}).get("url", "")
            if url:
                image_urls.append(url)
    return "".join(text_parts).strip(), image_urls


async def _download_image(url: str) -> bytes | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            return r.content
    except Exception as e:
        return None


# ── Group watcher (passive, stores all messages) ──

def _is_group(event: Event) -> bool:
    return getattr(event, "message_type", "") == "group"

group_watcher = on_message(_is_group, block=False)


@group_watcher.handle()
async def handle_group_watcher(event: Event):
    if memory is None:
        return
    text, _ = _extract_text_and_images(event)
    if not text:
        return
    await memory.save(
        f"group_{getattr(event, 'group_id', '')}",
        "user", text, event.get_user_id(),
    )


# ── Group @ chat ──

group_chat = on_message(_is_group & to_me(), block=True)


@group_chat.handle()
async def handle_group_chat(event: Event, bot: Bot):
    if agent is None or memory is None or guard is None:
        return

    user_id = event.get_user_id()
    group_id = str(getattr(event, "group_id", ""))
    chat_key = f"group_{group_id}"

    text, image_urls = _extract_text_and_images(event)

    # Handle reply/quote: extract from event.reply (OneBot V11 compat)
    reply_msg = getattr(event, "reply", None)
    if reply_msg is not None:
        quote_text = ""
        quote_urls: list[str] = []
        for seg in getattr(reply_msg, "message", []):
            seg_type = getattr(seg, "type", "")
            if seg_type == "text":
                quote_text += getattr(seg, "data", {}).get("text", "")
            elif seg_type == "image":
                url = getattr(seg, "data", {}).get("url", "")
                if url:
                    quote_urls.append(url)
        if quote_text:
            text = f"[引用消息] {quote_text}\n{text}" if text else f"[引用消息] {quote_text}"
        image_urls = quote_urls + image_urls

    if not text and not image_urls:
        logger.info("No text and no images, skipping")
        return

    # Rate check
    ok, reason = await guard.check_rate(user_id, group_id)
    if not ok:
        await group_chat.finish(MessageSegment.text(reason))

    # Get context
    ctx_msgs = await memory.get_context(chat_key, limit=30)
    ctx_text = _format_context(ctx_msgs)

    # Recall memories
    mem_text = await memory.recall(text, chat_key)

    # Run agent
    combined_context = ctx_text
    if mem_text:
        combined_context += f"\n[相关记忆]\n{mem_text}"

    response = await agent.run(
        text,
        image_urls=image_urls if image_urls else None,
        memory_context=combined_context,
        user_id=user_id,
        group_id=group_id,
    )

    resp_text = response.get("text", "")
    resp_images = response.get("images", [])

    if not resp_text and not resp_images:
        return

    # Save & update carry-over
    await memory.save(chat_key, "assistant", resp_text, "bot")
    _last_reply[f"{chat_key}:{user_id}"] = time.time()

    # Update profiles & extract facts
    await memory.update_profile(user_id, "", ctx_msgs[-10:])
    await memory.extract_and_remember(
        chat_key, ctx_msgs[-6:] + [{"role": "assistant", "content": resp_text}]
    )

    # Build response message with optional images (sent separately)
    if resp_images:
        if resp_text:
            await group_chat.send(MessageSegment.text(resp_text))
        for file_uri in resp_images:
            await group_chat.send(MessageSegment.image(file_uri))
        await group_chat.finish()
    else:
        await group_chat.finish(MessageSegment.text(resp_text))


# ── Private chat ──

def _is_private(event: Event) -> bool:
    return getattr(event, "message_type", "") == "private"

private_chat = on_message(_is_private, block=True)


@private_chat.handle()
async def handle_private_chat(event: Event, bot: Bot):
    if agent is None or memory is None or guard is None:
        return

    user_id = event.get_user_id()
    chat_key = f"private_{user_id}"

    text, image_urls = _extract_text_and_images(event)

    # Handle reply/quote: extract from event.reply (OneBot V11 compat)
    reply_msg = getattr(event, "reply", None)
    if reply_msg is not None:
        quote_text = ""
        quote_urls: list[str] = []
        for seg in getattr(reply_msg, "message", []):
            seg_type = getattr(seg, "type", "")
            if seg_type == "text":
                quote_text += getattr(seg, "data", {}).get("text", "")
            elif seg_type == "image":
                url = getattr(seg, "data", {}).get("url", "")
                if url:
                    quote_urls.append(url)
        if quote_text:
            text = f"[引用消息] {quote_text}\n{text}" if text else f"[引用消息] {quote_text}"
        image_urls = quote_urls + image_urls

    if not text and not image_urls:
        logger.info("No text and no images, skipping")
        return

    ok, reason = await guard.check_rate(user_id)
    if not ok:
        await private_chat.finish(MessageSegment.text(reason))

    ctx_msgs = await memory.get_context(chat_key, limit=15)
    ctx_text = _format_context(ctx_msgs)
    mem_text = await memory.recall(text, chat_key)

    response = await agent.run(
        text,
        image_urls=image_urls if image_urls else None,
        memory_context=f"{ctx_text}\n{mem_text}" if mem_text else ctx_text,
        user_id=user_id,
    )

    resp_text = response.get("text", "")
    resp_images = response.get("images", [])

    if not resp_text and not resp_images:
        return

    await memory.save(chat_key, "assistant", resp_text, "bot")
    _last_reply[f"{chat_key}:{user_id}"] = time.time()

    if resp_images:
        if resp_text:
            await private_chat.send(MessageSegment.text(resp_text))
        for file_uri in resp_images:
            await private_chat.send(MessageSegment.image(file_uri))
        await private_chat.finish()
    else:
        await private_chat.finish(MessageSegment.text(resp_text))


def _format_context(msgs: list[dict]) -> str:
    if not msgs:
        return ""
    lines = ["【最近对话】"]
    for m in msgs[-15:]:
        role = "Bot" if m["role"] == "assistant" else f"User_{m.get('user_id', '?')}"
        lines.append(f"{role}: {m['content'][:200]}")
    return "\n".join(lines)
