"""
定时内容插件：手动触发内容源获取。
"""

from nonebot import on_command

from qq_bot.scheduler import get_source, list_sources

cmd = on_command("scheduler", aliases={"定时任务", "内容"}, block=True)


@cmd.handle()
async def handle(event):
    args = event.get_message().extract_plain_text().strip().split()
    if not args:
        await cmd.finish(f"可用内容源：{', '.join(list_sources())}\n用法：/scheduler <源名>")

    source = get_source(args[0].strip().lower())
    if not source:
        await cmd.finish(f"未知内容源：{args[0]}，可用：{', '.join(list_sources())}")

    try:
        content = await source.fetch()
        await cmd.finish(f"【{source.name}】\n{content}")
    except Exception as e:
        await cmd.finish(f"获取失败：{str(e)}")
