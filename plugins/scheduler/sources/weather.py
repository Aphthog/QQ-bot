from .base import BaseSource


class WeatherSource(BaseSource):
    name = "weather"

    async def fetch(self) -> str:
        return "天气预报功能待实现，请配置天气 API"
