import httpx
import os
from .base import BaseSource


class WeatherSource(BaseSource):
    name = "weather"

    async def fetch(self) -> str:
        """
        获取天气预报
        使用 Open-Meteo API（免费，无需 API key）
        默认城市：上海 (经纬度可配置)
        """
        # 默认上海，可通过 WEATHER_LAT/WEATHER_LON 环境变量配置
        lat = os.getenv("WEATHER_LAT", "31.2304")
        lon = os.getenv("WEATHER_LON", "121.4737")
        city = os.getenv("WEATHER_CITY", "上海")

        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,weather_code,wind_speed_10m"
                f"&timezone=Asia%2FShanghai"
            )

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            current = data.get("current", {})
            temp = current.get("temperature_2m", "?")
            weather_code = current.get("weather_code", 0)
            wind = current.get("wind_speed_10m", "?")

            weather_desc = _weather_code_to_desc(weather_code)

            return (
                f"🌤️ {city}当前天气\n"
                f"温度：{temp}°C\n"
                f"天气：{weather_desc}\n"
                f"风速：{wind} km/h"
            )

        except Exception as e:
            return f"天气获取失败：{str(e)}"


def _weather_code_to_desc(code: int) -> str:
    """将天气码转为中文描述"""
    mapping = {
        0: "晴",
        1: "晴间多云",
        2: "多云",
        3: "阴",
        45: "雾",
        48: "雾凇",
        51: "小毛毛雨",
        53: "中毛毛雨",
        55: "大毛毛雨",
        61: "小雨",
        63: "中雨",
        65: "大雨",
        71: "小雪",
        73: "中雪",
        75: "大雪",
        80: "小阵雨",
        81: "中阵雨",
        82: "大阵雨",
        95: "雷暴",
        96: "雷暴伴小冰雹",
        99: "雷暴伴大冰雹",
    }
    return mapping.get(code, f"代码{code}")
