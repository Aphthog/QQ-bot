"""Image generation tool via GLM-Image API."""
from __future__ import annotations

import logging

import httpx

from qq_bot.config import config
from qq_bot.tools.registry import tool

logger = logging.getLogger("qq_bot.tools.image_gen")

# Import the pending-images store from agent core
from qq_bot.agent.core import _pending_images  # noqa: E402

GLM_IMAGE_URL = f"{config.GLM_BASE_URL}/images/generations"
DEFAULT_SIZE = "1024x1024"


@tool(
    name="generate_image",
    description="使用AI生成图片。适用：用户要求画图、生成图片、制作海报等。"
    "参数prompt应详细描述画面内容、风格、构图，中文为主。",
    params={
        "prompt": (str, "图片描述（中文，详细描述画面内容、风格、构图、文字等）"),
        "size": (str, f"图片尺寸，默认{DEFAULT_SIZE}，可选：1568x1056/1056x1568/1472x1088/1088x1472/1728x960/960x1728"),
    },
    category="core",
    timeout=180,
)
async def generate_image(prompt: str, size: str = DEFAULT_SIZE) -> str:
    if not prompt or not prompt.strip():
        return "[图片生成: 描述不能为空]"

    if len(prompt) > 1000:
        prompt = prompt[:1000]

    headers = {
        "Authorization": f"Bearer {config.GLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "glm-image",
        "prompt": prompt.strip(),
        "size": size or DEFAULT_SIZE,
    }

    logger.info(f"Generating image: {prompt[:50]}... size={size}")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(GLM_IMAGE_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(f"GLM-Image API error: {resp.status_code} {resp.text[:300]}")
                try:
                    err_data = resp.json()
                    err_code = err_data.get("error", {}).get("code", "")
                    err_msg = err_data.get("error", {}).get("message", "")
                    if err_code == "1301":
                        return "[图片生成: 内容审核未通过，请换个描述试试]"
                    if err_msg:
                        return f"[图片生成失败: {err_msg}]"
                except Exception:
                    pass
                return "[图片生成失败: API返回错误]"
            data = resp.json()
    except httpx.TimeoutException:
        return "[图片生成超时，请稍后重试]"
    except Exception as e:
        logger.error(f"GLM-Image API call failed: {e}")
        return f"[图片生成失败: {e}]"

    try:
        image_url = data["data"][0]["url"]
    except (KeyError, IndexError, TypeError):
        logger.error(f"Unexpected response format: {data}")
        return "[图片生成失败: 响应格式异常]"

    if not image_url:
        return "[图片生成失败: 未获取到图片URL]"

    # Pass the CDN URL directly — Lagrange downloads it
    _pending_images.append(image_url)

    return f"[图片已生成] 尺寸{size}"
