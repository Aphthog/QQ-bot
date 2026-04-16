import httpx
import os
from urllib.parse import quote


async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> str:
    """
    调用 Pollinations AI 生成图片，返回图片 URL。
    Pollinations 完全免费，无需 API key。

    Args:
        prompt: 图片描述
        width: 宽度，默认 1024
        height: 高度，默认 1024

    Returns:
        str: 图片 URL
    """
    api_key = os.getenv("POLLINATIONS_API_KEY", "")
    encoded_prompt = quote(prompt)

    if api_key:
        # 使用 API key（付费模式）
        try:
            url = f"https://api.pollinations.ai/v2/image"
            payload = {
                "prompt": prompt,
                "width": width,
                "height": height,
                "nologo": True,
                "seed": None,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json().get("url", "")
                if result:
                    return result
        except Exception:
            pass  # 付费路径失败，兜底到免费 URL

    # 免费模式，官方推荐 path 格式
    return (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={width}"
        f"&height={height}"
        f"&nologo=true"
    )
