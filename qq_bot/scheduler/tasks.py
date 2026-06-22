"""Scheduled tasks using nonebot-plugin-apscheduler."""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger("qq_bot.scheduler")


class ScheduledTask:
    """Wrapper for a scheduled agent action."""

    def __init__(
        self,
        name: str,
        trigger: str = "cron",
        hour: int = 8,
        minute: int = 0,
        action: str = "",
        target_groups: list[str] | None = None,
    ):
        self.name = name
        self.trigger = trigger
        self.hour = hour
        self.minute = minute
        self.action = action
        self.target_groups = target_groups or ["*"]

    def to_trigger_args(self) -> dict:
        return {"trigger": self.trigger, "hour": self.hour, "minute": self.minute}


# Registry of scheduled tasks — extend by appending to this list
SCHEDULED_TASKS: list[ScheduledTask] = []


def register_scheduled_tasks(scheduler, agent_loop, bot):
    """Register all scheduled tasks with APScheduler."""
    for task in SCHEDULED_TASKS:
        async def _execute(t=task):
            logger.info(f"Scheduler: running task '{t.name}'")
            result = await agent_loop.run(
                f"执行定时任务: {t.action}" if t.action else "生成今日简报",
                group_id="",
                user_id="system",
            )
            if t.target_groups == ["*"]:
                logger.info(f"Task '{t.name}' result: {result[:100]}...")
            else:
                for gid in t.target_groups:
                    await bot.send_group_msg(group_id=int(gid), message=result)

        scheduler.add_job(
            _execute,
            **task.to_trigger_args(),
            id=task.name,
            replace_existing=True,
        )
    logger.info(f"Scheduler: registered {len(SCHEDULED_TASKS)} tasks")
