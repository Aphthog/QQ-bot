"""
广播管理插件：添加/移除广播群、即时广播、定时推送。
"""

import json
import os
from pathlib import Path

import nonebot
from nonebot import get_bot, get_driver, on_command, require
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageSegment

from qq_bot.config import settings as s
from qq_bot.scheduler import get_source

scheduler = require("nonebot_plugin_apscheduler").scheduler

DATA_DIR = Path(__file__).parent.parent.parent / "data"
GROUPS_FILE = DATA_DIR / "broadcast_groups.json"


def _load_groups() -> list[int]:
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_groups(groups: list[int]):
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)


broadcast_cmd = on_command("broadcast", aliases={"广播"}, block=True, priority=1)


@broadcast_cmd.handle()
async def handle_broadcast(event: Event):
    args = event.get_message().extract_plain_text().strip().split()
    if not args:
        await broadcast_cmd.finish(
            "广播命令用法：\n"
            "/broadcast add <群号> - 添加群\n"
            "/broadcast remove <群号> - 移除群\n"
            "/broadcast list - 查看群列表\n"
            "/broadcast now <内容> - 立即广播"
        )

    sub = args[0].lower()
    groups = _load_groups()

    if sub == "add":
        if len(args) < 2:
            await broadcast_cmd.finish("请提供群号：/broadcast add <群号>")
        try:
            gid = int(args[1])
        except ValueError:
            await broadcast_cmd.finish("群号必须是数字")
        if gid not in groups:
            groups.append(gid)
            _save_groups(groups)
            await broadcast_cmd.finish(f"已添加群 {gid}，当前共 {len(groups)} 个群")
        await broadcast_cmd.finish(f"群 {gid} 已在列表中")

    elif sub == "remove":
        if len(args) < 2:
            await broadcast_cmd.finish("请提供群号：/broadcast remove <群号>")
        try:
            gid = int(args[1])
        except ValueError:
            await broadcast_cmd.finish("群号必须是数字")
        if gid in groups:
            groups.remove(gid)
            _save_groups(groups)
            await broadcast_cmd.finish(f"已移除群 {gid}，当前共 {len(groups)} 个群")
        await broadcast_cmd.finish(f"群 {gid} 不在列表中")

    elif sub == "list":
        if not groups:
            await broadcast_cmd.finish("广播列表为空")
        await broadcast_cmd.finish("广播群列表：\n" + "\n".join(f"- {g}" for g in groups))

    elif sub == "now":
        if len(args) < 2:
            await broadcast_cmd.finish("请提供广播内容：/broadcast now <内容>")
        content = " ".join(args[1:])
        bot = get_bot()
        ok = fail = 0
        for gid in groups:
            try:
                await bot.send_group_msg(group_id=gid, message=MessageSegment.text(content))
                ok += 1
            except Exception:
                fail += 1
        await broadcast_cmd.finish(f"广播完成：成功 {ok} 群，失败 {fail} 群")
    else:
        await broadcast_cmd.finish(f"未知命令：{sub}")


# ── 定时广播 ──

async def _scheduled_broadcast():
    from nonebot import get_bot

    content_types = [c.strip() for c in s.BROADCAST_CONTENT_TYPES if c.strip()]
    groups = _load_groups()
    if not groups:
        return

    bot = get_bot()
    parts = []
    for ctype in content_types:
        source = get_source(ctype)
        if source:
            try:
                content = await source.fetch()
                parts.append(f"【{source.name}】\n{content}")
            except Exception:
                parts.append(f"【{ctype}】获取失败")

    text = "\n\n".join(parts)
    for gid in groups:
        try:
            await bot.send_group_msg(group_id=gid, message=MessageSegment.text(text))
        except Exception:
            pass


def _setup_scheduler():
    times = [t.strip() for t in s.BROADCAST_SCHEDULE.split(",") if t.strip()]
    for t in times:
        if ":" in t:
            h, m = t.split(":", 1)
            scheduler.add_job(_scheduled_broadcast, "cron", hour=int(h), minute=int(m), id=f"broadcast_{t}", replace_existing=True)


get_driver().on_startup(_setup_scheduler)
