import nonebot
from nonebot import on_command, on_message
from nonebot.adapters import Event
from nonebot.adapters.llonebot import MessageSegment

from llm_adapter import get_adapter
import os

llm = get_adapter(os.getenv("LLM_PROVIDER", "ollama"))

chat_handler = on_message(block=True)


@chat_handler.handle()
async def handle_chat(event: Event):
    text = str(event.get_message()).strip()
    if not text:
        return

    user_id = event.get_user_id()
    session_id = f"chat:history:{user_id}"

    history = []

    response = await llm.chat(prompt=text, context=history)
    await chat_handler.finish(MessageSegment.text(response))
