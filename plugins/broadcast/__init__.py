import nonebot
from nonebot import on_command
from nonebot.adapters import Event
import json
import os

broadcast_handler = on_command("broadcast", aliases={"广播"})


@broadcast_handler.handle()
async def handle_broadcast(event: Event):
    groups_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "broadcast_groups.json")
    with open(groups_file, "r", encoding="utf-8") as f:
        groups = json.load(f)

    message = str(event.get_message()).strip()
    if not message:
        await broadcast_handler.finish("请提供广播内容")

    from nonebot.adapters.llonebot import MessageSegment
    for group_id in groups:
        try:
            await nonebot.get_bot().send_group_msg(group_id=int(group_id), message=MessageSegment.text(message))
        except Exception as e:
            pass

    await broadcast_handler.finish(f"广播已发送到 {len(groups)} 个群")
