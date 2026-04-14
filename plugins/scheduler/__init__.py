from nonebot import on_command
from .sources import get_source

scheduler_handler = on_command("scheduler", aliases={"定时任务"})


@scheduler_handler.handle()
async def handle_scheduler(event):
    args = str(event.get_message()).strip().split()
    if not args:
        await scheduler_handler.finish("用法: /scheduler <news|weather|custom>")
    source_name = args[0]
    source = get_source(source_name)
    if source:
        content = await source.fetch()
        await scheduler_handler.finish(content)
    else:
        await scheduler_handler.finish(f"未知内容源: {source_name}")
