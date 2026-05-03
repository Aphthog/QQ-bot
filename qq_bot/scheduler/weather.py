"""天气源（Open-Meteo，免费无需 key）"""

import httpx

from qq_bot.config import settings
from .base import BaseSource


class WeatherSource(BaseSource):
    name = "weather"

    async def fetch(self) -> str:
        lat = settings.WEATHER_LAT
        lon = settings.WEATHER_LON
        city = settings.WEATHER_CITY

        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,weather_code,wind_speed_10m"
                f"&timezone=Asia%2FShanghai"
            )
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            current = data.get("current", {})
            temp = current.get("temperature_2m", "?")
            code = current.get("weather_code", 0)
            wind = current.get("wind_speed_10m", "?")
            desc = _code_to_desc(code)

            return f"【{city}当前天气】\n温度：{temp}°C\n天气：{desc}\n风速：{wind} km/h"
        except Exception as e:
            return f"天气获取失败：{str(e)}"


def _code_to_desc(code: int) -> str:
    mapping = {
        0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
        45: "雾", 48: "雾凇",
        51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
        95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
    }
    return mapping.get(code, f"代码{code}")
