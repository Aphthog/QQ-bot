"""
Weather Skill - 查询天气（使用和风天气API）
"""

import httpx
import os
from llm_adapter import get_adapter


class WeatherSkill:
    """查询城市天气"""

    async def execute(self, params: dict) -> str:
        """
        执行天气查询
        params: {"city": "北京"}
        """
        city = params.get("city", "").strip()
        if not city:
            return "请提供要查询的城市，格式：/weather <城市>"

        api_key = os.getenv("QWEATHER_API_KEY", "")
        if not api_key:
            return "天气API未配置，请联系管理员设置 QWEATHER_API_KEY 环境变量"

        api_host = os.getenv("QWEATHER_API_HOST", "")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. 搜索城市 location ID
                geo_url = f"https://{api_host}/geo/v2/city/lookup?location={city}&key={api_key}"
                geo_resp = await client.get(geo_url)
                if geo_resp.status_code != 200:
                    return f"城市搜索失败，请检查API配置"

                geo_data = geo_resp.json()
                location_list = geo_data.get("location", [])
                if not location_list:
                    return f"未找到城市：{city}，请尝试更具体的名称（如北京朝阳）"

                # 取第一个匹配结果（最相关的）
                location = location_list[0]
                location_id = location.get("id")
                location_name = location.get("name", city)
                location_admin = location.get("adminArea", "")
                location_country = location.get("country", "")

                # 2. 获取实时天气
                weather_url = f"https://{api_host}/v7/weather/now?location={location_id}&key={api_key}"
                weather_resp = await client.get(weather_url)
                if weather_resp.status_code != 200:
                    return f"天气查询失败，请稍后重试"

                weather_data = weather_resp.json()
                now = weather_data.get("now", {})

                temp = now.get("temp", "")
                feels_like = now.get("feelsLike", "")
                desc = now.get("text", "")
                humidity = now.get("humidity", "")
                wind_speed = now.get("windSpeed", "")
                wind_dir = now.get("windDir", "")
                visibility = now.get("vis", "")
                pressure = now.get("pressure", "")
                uv_index = now.get("uvIndex", "")

                # 格式化输出
                full_location = f"{location_name}"
                if location_admin and location_admin != location_name:
                    full_location += f"（{location_admin}）"
                if location_country and location_country != "中国":
                    full_location += f"，{location_country}"

                weather_info = f"""【{full_location}】实时天气
🌡️ 温度：{temp}°C（体感{feels_like}°C）
☁️ 状况：{desc}
💧 湿度：{humidity}%
🌬️ 风速：{wind_speed}km/h（{wind_dir}）
👁️ 能见度：{visibility}km
☀️ 紫外线：{uv_index}
🔵 气压：{pressure}hPa"""

                # 3. 调 LLM 生成出行建议
                llm = get_adapter(os.getenv("LLM_PROVIDER", "ollama"))
                suggestion_prompt = f"""根据以下天气数据，生成3-5条出行建议。

天气数据：
- 温度：{temp}°C（体感{feels_like}°C）
- 天气状况：{desc}
- 湿度：{humidity}%
- 风速：{wind_speed}km/h（{wind_dir}）
- 紫外线指数：{uv_index}
- 能见度：{visibility}km

要求：简洁实用，针对性强，比如穿衣、带伞、防晒等。直接输出建议，不要解释。"""

                suggestions = await llm.chat(
                    prompt=suggestion_prompt,
                    context=[],
                    system_prompt="你是贴心的天气助手，生成简洁的出行建议，直接输出建议，每条建议不超过20字。",
                    max_tokens=200,
                )

                return f"{weather_info}\n\n📌 出行建议：\n{suggestions}"

        except httpx.TimeoutException:
            return "天气查询超时，请稍后重试"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"查询天气失败：{str(e)}"