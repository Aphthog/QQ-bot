import nonebot
from nonebot import on_command, scheduler
from nonebot.adapters import Event
import os

admin_handler = on_command("admin", aliases={"管理员"})


@admin_handler.handle()
async def handle_admin(event: Event):
    args = str(event.get_message()).strip().split()
    if not args:
        await admin_handler.finish("可用命令: /admin add_group <group_id>, /admin remove_group <group_id>, /admin list_groups")

    cmd = args[0]
    if cmd == "add_group":
        if len(args) < 2:
            await admin_handler.finish("用法: /admin add_group <group_id>")
        group_id = args[1]
        import json
        groups_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "broadcast_groups.json")
        with open(groups_file, "r", encoding="utf-8") as f:
            groups = json.load(f)
        if group_id not in groups:
            groups.append(group_id)
            with open(groups_file, "w", encoding="utf-8") as f:
                json.dump(groups, f, ensure_ascii=False)
        await admin_handler.finish(f"已添加群 {group_id}")
    elif cmd == "remove_group":
        if len(args) < 2:
            await admin_handler.finish("用法: /admin remove_group <group_id>")
        group_id = args[1]
        import json
        groups_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "broadcast_groups.json")
        with open(groups_file, "r", encoding="utf-8") as f:
            groups = json.load(f)
        if group_id in groups:
            groups.remove(group_id)
            with open(groups_file, "w", encoding="utf-8") as f:
                json.dump(groups, f, ensure_ascii=False)
        await admin_handler.finish(f"已移除群 {group_id}")
    elif cmd == "list_groups":
        import json
        groups_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "broadcast_groups.json")
        with open(groups_file, "r", encoding="utf-8") as f:
            groups = json.load(f)
        await admin_handler.finish(f"当前群列表: {', '.join(groups) if groups else '空'}")
    else:
        await admin_handler.finish("未知命令")
