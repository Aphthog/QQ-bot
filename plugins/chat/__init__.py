from nonebot import on_message, on_command
from nonebot.adapters import Event
from nonebot.adapters.llonebot import MessageSegment, At, Message
import os
import json

from llm_adapter import get_adapter

llm = get_adapter(os.getenv("LLM_PROVIDER", "ollama"))


def _load_history(user_id: str) -> list[dict]:
    """从 JSON 文件加载对话历史"""
    history_file = os.getenv("HISTORY_FILE", "data/chat_history.json")
    max_turns = int(os.getenv("HISTORY_MAX_TURNS", "10"))

    # 确保目录存在
    os.makedirs(os.path.dirname(history_file) if os.path.dirname(history_file) else ".", exist_ok=True)

    # 尝试读取现有历史
    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                all_history = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        all_history = {}

    # 获取该用户的历史，保留最近 N 轮
    history = all_history.get(user_id, [])[-max_turns:]
    return history


def _save_history(user_id: str, history: list[dict]):
    """保存对话历史到 JSON 文件"""
    history_file = os.getenv("HISTORY_FILE", "data/chat_history.json")
    max_turns = int(os.getenv("HISTORY_MAX_TURNS", "10"))

    os.makedirs(os.path.dirname(history_file) if os.path.dirname(history_file) else ".", exist_ok=True)

    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                all_history = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        all_history = {}

    # 保留最近 N 轮
    all_history[user_id] = history[-max_turns:]

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(all_history, f, ensure_ascii=False, indent=2)


def _is_mentioned_bot(event: Event) -> bool:
    """检测消息是否 @ 了 bot"""
    message = event.get_message()
    for seg in message:
        if seg.type == "at" and seg.data.get("qq") == "all":
            return True
    return False


chat_cmd = on_command("chat", aliases={"聊天", "问"}, block=True)


@chat_cmd.handle()
async def handle_chat_cmd(event: Event):
    """处理私聊或 /chat 命令"""
    user_id = event.get_user_id()
    text = event.get_message().extract_plain_text()

    if not text:
        await chat_cmd.finish("请输入问题，例如：/chat 你好")

    # 加载历史
    history = _load_history(user_id)

    # 调用 LLM
    response = await llm.chat(prompt=text, context=history)

    # 保存历史
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    _save_history(user_id, history)

    await chat_cmd.finish(MessageSegment.text(response))


# @bot 触发（群聊中使用 @bot）
group_chat = on_message(block=True)


@group_chat.handle()
async def handle_group_chat(event: Event):
    """处理群聊 @bot 消息"""
    # 检查是否 @ 了 bot
    if not _is_mentioned_bot(event):
        return  # 没有 @bot，不处理

    user_id = event.get_user_id()
    text = event.get_message().extract_plain_text()

    if not text:
        return

    # 加载历史
    history = _load_history(user_id)

    # 调用 LLM
    response = await llm.chat(prompt=text, context=history)

    # 保存历史
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": response})
    _save_history(user_id, history)

    await group_chat.finish(MessageSegment.text(response))
