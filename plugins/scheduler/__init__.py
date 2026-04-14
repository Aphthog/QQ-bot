from nonebot import on_command
from .sources import get_source, list_sources

scheduler_cmd = on_command("scheduler", aliases={"定时任务", "内容"}, block=True)


@scheduler_cmd.handle()
async def handle_scheduler(event):
    """手动触发内容获取：/scheduler <news|weather|custom>"""
    args = event.get_message().extract_plain_text().strip().split()

    if not args:
        available = list_sources()
        await scheduler_cmd.finish(
            f"可用内容源：{', '.join(available)}\n"
            "用法：/scheduler <源名>\n"
            "例如：/scheduler news"
        )

    source_name = args[0].strip().lower()
    source = get_source(source_name)

    if not source:
        available = list_sources()
        await scheduler_cmd.finish(
            f"未知内容源：{source_name}\n"
            f"可用：{', '.join(available)}"
        )

    try:
        content = await source.fetch()
        await scheduler_cmd.finish(f"【{source.name}】\n{content}")
    except Exception as e:
        await scheduler_cmd.finish(f"获取失败：{str(e)}")
