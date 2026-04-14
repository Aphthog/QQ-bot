from nonebot import on_command, require, get_bot
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageSegment
import nonebot
import json
import os
from pathlib import Path

# 加载调度器
scheduler = require("nonebot_plugin_apscheduler").scheduler

# 数据文件路径
DATA_DIR = Path(__file__).parent.parent.parent / "data"
GROUPS_FILE = DATA_DIR / "broadcast_groups.json"


def _load_groups() -> list[int]:
    """加载广播群列表"""
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_groups(groups: list[int]):
    """保存广播群列表"""
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)


# === 广播命令 ===
broadcast_cmd = on_command("broadcast", aliases={"广播"}, block=True)


@broadcast_cmd.handle()
async def handle_broadcast(event: Event):
    """广播命令：/broadcast add|remove|list <group_id>"""
    args = event.get_message().extract_plain_text().strip().split()

    if not args:
        await broadcast_cmd.finish(
            "广播命令用法：\n"
            "/broadcast add <群号> - 添加群\n"
            "/broadcast remove <群号> - 移除群\n"
            "/broadcast list - 查看群列表\n"
            "/broadcast now <内容> - 立即广播"
        )

    sub_cmd = args[0].lower()
    groups = _load_groups()

    if sub_cmd == "add":
        if len(args) < 2:
            await broadcast_cmd.finish("请提供群号：/broadcast add <群号>")
        try:
            group_id = int(args[1])
        except ValueError:
            await broadcast_cmd.finish("群号必须是数字")
        if group_id not in groups:
            groups.append(group_id)
            _save_groups(groups)
            await broadcast_cmd.finish(f"已添加群 {group_id}，当前共 {len(groups)} 个群")
        else:
            await broadcast_cmd.finish(f"群 {group_id} 已在列表中")

    elif sub_cmd == "remove":
        if len(args) < 2:
            await broadcast_cmd.finish("请提供群号：/broadcast remove <群号>")
        try:
            group_id = int(args[1])
        except ValueError:
            await broadcast_cmd.finish("群号必须是数字")
        if group_id in groups:
            groups.remove(group_id)
            _save_groups(groups)
            await broadcast_cmd.finish(f"已移除群 {group_id}，当前共 {len(groups)} 个群")
        else:
            await broadcast_cmd.finish(f"群 {group_id} 不在列表中")

    elif sub_cmd == "list":
        if not groups:
            await broadcast_cmd.finish("广播列表为空")
        msg = "广播群列表：\n" + "\n".join(f"- {g}" for g in groups)
        await broadcast_cmd.finish(msg)

    elif sub_cmd == "now":
        if len(args) < 2:
            await broadcast_cmd.finish("请提供广播内容：/broadcast now <内容>")
        content = " ".join(args[1:])
        bot = get_bot()
        success = 0
        failed = 0
        for gid in groups:
            try:
                await bot.send_group_msg(group_id=gid, message=MessageSegment.text(content))
                success += 1
            except Exception:
                failed += 1
        await broadcast_cmd.finish(f"广播完成：成功 {success} 群，失败 {failed} 群")

    else:
        await broadcast_cmd.finish(f"未知命令：{sub_cmd}，用法：/broadcast add|remove|list|now")


# === 定时广播任务 ===
async def _scheduled_broadcast():
    """定时广播任务，由 apscheduler 调用"""
    from plugins.scheduler.sources import get_source
    from nonebot import get_bot

    content_types = os.getenv("BROADCAST_CONTENT_TYPES", "news,weather,custom").split(",")
    groups = _load_groups()
    if not groups:
        return

    bot = get_bot()
    content_parts = []

    for ctype in content_types:
        ctype = ctype.strip()
        source = get_source(ctype)
        if source:
            try:
                content = await source.fetch()
                content_parts.append(f"【{source.name}】\n{content}")
            except Exception as e:
                content_parts.append(f"【{ctype}】获取失败")

    full_content = "\n\n".join(content_parts)

    for gid in groups:
        try:
            await bot.send_group_msg(group_id=gid, message=MessageSegment.text(full_content))
        except Exception:
            pass


# === 注册定时任务 ===
def _setup_scheduler():
    """从配置注册定时广播任务"""
    schedule_str = os.getenv("BROADCAST_SCHEDULE", "8:00,12:00,18:00")
    times = [t.strip() for t in schedule_str.split(",") if t.strip()]

    for t in times:
        if ":" in t:
            hour, minute = t.split(":", 1)
            scheduler.add_job(
                _scheduled_broadcast,
                "cron",
                hour=int(hour),
                minute=int(minute),
                id=f"broadcast_{t}",
                replace_existing=True,
            )


# NoneBot 启动时注册定时任务
nonebot = require("nonebot")
nonebot.on_startup(_setup_scheduler)
