from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, params: dict, context: dict | None = None) -> str:
        ...

    async def _get_group_card(self, params: dict, user_id: str) -> str:
        """获取群成员群名片，取不到则返回 QQ 号。"""
        bot = params.get("bot")
        group_id = params.get("group_id", "")
        if not bot or not group_id:
            return user_id
        try:
            info = await bot.get_group_member_info(
                group_id=int(group_id), user_id=int(user_id), no_cache=True
            )
            return info.get("card", "") or info.get("nickname", "") or user_id
        except Exception:
            return user_id
