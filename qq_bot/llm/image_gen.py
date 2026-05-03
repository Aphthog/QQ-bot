"""Pollinations AI 图片生成（免费，无需 key）"""

import httpx
from urllib.parse import quote

from qq_bot.config import settings


async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> str:
    api_key = settings.POLLINATIONS_API_KEY
    encoded = quote(prompt)

    if api_key:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.pollinations.ai/v2/image",
                    json={"prompt": prompt, "width": width, "height": height, "nologo": True},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                url = resp.json().get("url", "")
                if url:
                    return url
        except Exception:
            pass

    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
