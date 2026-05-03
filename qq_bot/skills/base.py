from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, params: dict, context: dict | None = None) -> str:
        ...
