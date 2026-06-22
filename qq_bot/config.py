"""Centralized config, loaded from env vars."""
from __future__ import annotations

import json
import os
from functools import cached_property


class Config:
    """Application-wide config. Singleton via module-level `config` instance."""

    _instance: Config | None = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # Bot
    BOT_NAME: str = os.getenv("BOT_NAME", "小y")
    BOT_QQ: str = os.getenv("BOT_QQ", "")

    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "glm")
    GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
    GLM_MODEL: str = os.getenv("GLM_MODEL", "glm-4.6v")
    GLM_BASE_URL: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    # Search
    SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "searxng")
    SEARXNG_BASE_URL: str = os.getenv("SEARXNG_BASE_URL", "http://localhost:8888")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Agent
    AGENT_MAX_PLAN_STEPS: int = int(os.getenv("AGENT_MAX_PLAN_STEPS", "5"))
    AGENT_MAX_RETRY: int = int(os.getenv("AGENT_MAX_RETRY", "2"))
    AGENT_TOOL_TIMEOUT: float = float(os.getenv("AGENT_TOOL_TIMEOUT", "15"))
    MAX_RESPONSE_TOKENS: int = int(os.getenv("MAX_RESPONSE_TOKENS", "1024"))

    # Admin
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "change_me")

    @cached_property
    def SUPERUSERS(self) -> list[str]:
        raw = os.getenv("SUPERUSERS", "[]")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [raw] if raw else []

    # Storage
    DB_PATH: str = os.getenv("DB_PATH", "data/qq_bot.db")
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "data/chroma")

    # Debug
    @property
    def DEBUG_MODE(self) -> bool:
        return os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Session carry-over window (seconds)
    SESSION_CARRY_WINDOW: int = int(os.getenv("SESSION_CARRY_WINDOW", "10"))


config = Config()
