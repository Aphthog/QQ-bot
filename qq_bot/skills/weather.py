"""
Weather Skill - 查询天气（和风天气 API）
"""

import httpx

from qq_bot.config import settings
from qq_bot.llm import get_adapter
from .base import BaseSkill


class WeatherSkill(BaseSkill):
    name = "weather"
    description = "查询城市天气"

    async def execute(self, params: dict, context: dict | None = None) -> str:
        city = params.get("city", "").strip()
        if not city:
            return "请提供要查询的城市，格式：/weather <城市>"

        api_key = settings.QWEATHER_API_KEY
        api_host = settings.QWEATHER_API_HOST
        if not api_key:
            return "天气API未配置，请联系管理员设置 QWEATHER_API_KEY"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                geo_resp = await client.get(
                    f"https://{api_host}/geo/v2/city/lookup?location={city}&key={api_key}"
                )
                if geo_resp.status_code != 200:
                    return "城市搜索失败，请检查API配置"
                geo_data = geo_resp.json()
                location_list = geo_data.get("location", [])
                if not location_list:
                    return f"未找到城市：{city}，请尝试更具体的名称（如北京朝阳）"

                loc = location_list[0]
                lid = loc["id"]
                lname = loc.get("name", city)
                ladmin = loc.get("adminArea", "")
                lcountry = loc.get("country", "")

                weather_resp = await client.get(
                    f"https://{api_host}/v7/weather/now?location={lid}&key={api_key}"
                )
                if weather_resp.status_code != 200:
                    return "天气查询失败，请稍后重试"
                now = weather_resp.json().get("now", {})

                full_loc = lname
                if ladmin and ladmin != lname:
                    full_loc += f"（{ladmin}）"
                if lcountry and lcountry != "中国":
                    full_loc += f"，{lcountry}"

                weather_info = (
                    f"📍【{full_loc}】实时天气\n"
                    f"🌡️ 温度：{now.get('temp', '?')}°C（体感{now.get('feelsLike', '?')}°C）\n"
                    f"☁️ 状况：{now.get('text', '?')}\n"
                    f"💧 湿度：{now.get('humidity', '?')}%\n"
                    f"🌬️ 风速：{now.get('windSpeed', '?')}km/h（{now.get('windDir', '?')}）\n"
                    f"👁️ 能见度：{now.get('vis', '?')}km\n"
                    f"☀️ 紫外线：{now.get('uvIndex', '?')}\n"
                    f"📊 气压：{now.get('pressure', '?')}hPa"
                )

                llm = get_adapter(settings.LLM_PROVIDER)
                suggestions = await llm.chat(
                    prompt=(
                        f"根据以下天气数据，生成3-5条出行建议。\n\n"
                        f"温度：{now.get('temp', '?')}°C（体感{now.get('feelsLike', '?')}°C）\n"
                        f"天气状况：{now.get('text', '?')}\n"
                        f"湿度：{now.get('humidity', '?')}%\n"
                        f"风速：{now.get('windSpeed', '?')}km/h（{now.get('windDir', '?')}）\n"
                        f"紫外线指数：{now.get('uvIndex', '?')}\n"
                        f"能见度：{now.get('vis', '?')}km\n\n"
                        "要求：简洁实用，针对性强，直接输出建议，每条不超过20字。"
                    ),
                    context=[],
                    system_prompt="你是贴心的天气助手，生成简洁的出行建议。",
                    max_tokens=200,
                )
                return f"{weather_info}\n\n出行建议：\n{suggestions}"

        except httpx.TimeoutException:
            return "天气查询超时，请稍后重试"
