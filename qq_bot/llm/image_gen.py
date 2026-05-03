"""ComfyUI（NoobAI-XL）本地生图 → 返回 base64"""

import asyncio
import base64
import json
import os
import random

import httpx

from qq_bot.llm import get_adapter
from qq_bot.config import settings

_WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "noobai_workflow.json")

with open(_WORKFLOW_PATH) as f:
    _WORKFLOW_TEMPLATE = json.load(f)

_TRANSLATE_SYSTEM = (
    "Translate Chinese image descriptions into English Danbooru-style tags. "
    "Output only comma-separated tags, no explanation. "
    "Use booru conventions: 1girl/1boy for people, specify animal names for animals, "
    "include style, action, background, and quality descriptors when implied."
)


async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> str:
    """生成图片，返回可直接传给 MessageSegment.image 的 base64 字符串。"""
    # Translate Chinese prompt to English booru tags via LLM
    booru_prompt = await _translate_prompt(prompt)

    base_url = settings.COMFYUI_BASE_URL

    workflow = _deep_copy_workflow(_WORKFLOW_TEMPLATE)
    workflow["6"]["inputs"]["text"] = booru_prompt
    workflow["3"]["inputs"]["seed"] = random.randint(0, 2**31 - 1)
    workflow["5"]["inputs"]["width"] = _snap_size(width)
    workflow["5"]["inputs"]["height"] = _snap_size(height)

    async with httpx.AsyncClient(timeout=600.0, trust_env=False) as client:
        try:
            resp = await client.post(
                f"{base_url}/prompt",
                json={"prompt": workflow, "client_id": "qq-bot"},
            )
            resp.raise_for_status()
            prompt_id = resp.json()["prompt_id"]
        except httpx.HTTPError as e:
            return f"ComfyUI connection failed: {e}"

        for _ in range(300):
            await asyncio.sleep(1)
            hist_resp = await client.get(f"{base_url}/history/{prompt_id}")
            if hist_resp.status_code == 200:
                data = hist_resp.json()
                if prompt_id in data:
                    outputs = data[prompt_id]["outputs"]
                    break
        else:
            return "Image generation timeout."

        for node_output in outputs.values():
            if "images" not in node_output:
                continue
            img = node_output["images"][0]
            filename = img["filename"]
            subfolder = img.get("subfolder", "")
            img_type = img.get("type", "output")

            params = f"filename={filename}&type={img_type}"
            if subfolder:
                params += f"&subfolder={subfolder}"

            img_resp = await client.get(f"{base_url}/view?{params}")
            img_resp.raise_for_status()
            b64 = base64.b64encode(img_resp.content).decode()
            return f"base64://{b64}"

    return "Image generation failed."


async def _translate_prompt(raw: str) -> str:
    """将中文提示词翻译为英文 Danbooru 标签 + 品质前缀。"""
    try:
        llm = get_adapter()
        tags = await llm.chat(prompt=raw, system_prompt=_TRANSLATE_SYSTEM, max_tokens=100)
        tags = tags.strip().strip('"').strip("'")
    except Exception:
        tags = raw

    return f"masterpiece, best quality, very aesthetic, absurdres, {tags}"


def _snap_size(px: int) -> int:
    return max(64, (px + 32) // 64 * 64)


def _deep_copy_workflow(wf: dict) -> dict:
    return json.loads(json.dumps(wf))
