"""
集中配置入口。
所有模块通过 `from qq_bot.config import settings` 获取配置。
"""

from __future__ import annotations

import json
import os
from functools import cached_property


class Settings:
    DRIVER: str = os.getenv("DRIVER", "~fastapi")
    ONEBOT_ACCESS_TOKEN: str = os.getenv("ONEBOT_V11_ACCESS_TOKEN", "")

    # ── LLM ──
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "longcat")

    LONGCAT_API_KEY: str = os.getenv("LONGCAT_API_KEY", "")
    LONGCAT_MODEL: str = os.getenv("LONGCAT_MODEL", "LongCat-Flash-Omni-2603")
    LONGCAT_BASE_URL: str = os.getenv("LONGCAT_BASE_URL", "https://api.longcat.chat/openai/v1")

    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llava")
    OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "120"))

    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # ── 图片生成（ComfyUI）──
    COMFYUI_BASE_URL: str = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")

    # ── 天气（和风天气）──
    QWEATHER_API_KEY: str = os.getenv("QWEATHER_API_KEY", "")
    QWEATHER_API_HOST: str = os.getenv("QWEATHER_API_HOST", "devapi.qweather.com")

    # ── 聊天历史 ──
    HISTORY_DIR: str = os.getenv("HISTORY_DIR", "data/chats")

    @cached_property
    def GROUP_HISTORY_MAX_TURNS(self) -> int:
        return int(os.getenv("GROUP_HISTORY_MAX_TURNS", "1000"))

    @cached_property
    def USER_HISTORY_MAX_TURNS(self) -> int:
        return int(os.getenv("USER_HISTORY_MAX_TURNS", "15"))

    # ── 联网搜索 ──
    @property
    def ENABLE_WEB_SEARCH(self) -> bool:
        return os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"

    # ── Open-Meteo 天气 ──
    WEATHER_CITY: str = os.getenv("WEATHER_CITY", "上海")
    WEATHER_LAT: str = os.getenv("WEATHER_LAT", "31.2304")
    WEATHER_LON: str = os.getenv("WEATHER_LON", "121.4737")

    # ── Bot 身份 ──
    BOT_NAME: str = os.getenv("BOT_NAME") or os.getenv("Bot_Name", "小y")

    @cached_property
    def MAX_RESPONSE_TOKENS(self) -> int:
        return int(os.getenv("MAX_RESPONSE_TOKENS", "300"))

    # ── 管理员 ──
    @property
    def ADMIN_QQ(self) -> str:
        users = self.SUPERUSERS
        return users[0] if users else os.getenv("ADMIN_QQ", "")

    @cached_property
    def SUPERUSERS(self) -> list[str]:
        raw = os.getenv("SUPERUSERS", "[]")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [raw] if raw else []

    # ── 调试 ──
    @property
    def DEBUG_MODE(self) -> bool:
        return os.getenv("DEBUG_MODE", "false").lower() == "true"

    # ── RAG ──
    KNOWLEDGE_INDEX_PATH: str = os.getenv("KNOWLEDGE_INDEX_PATH", "data/knowledge_index")

    @cached_property
    def RAG_TOP_K(self) -> int:
        return int(os.getenv("RAG_TOP_K", "5"))

    @cached_property
    def RAG_SCORE_THRESHOLD(self) -> float:
        return float(os.getenv("RAG_SCORE_THRESHOLD", "120.0"))


settings = Settings()
