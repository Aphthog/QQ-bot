import os
import pytest
from qq_bot.config import Config


class TestConfig:
    def test_defaults(self):
        cfg = Config()
        assert cfg.BOT_NAME == "小y"
        assert cfg.LLM_PROVIDER == "glm"
        assert cfg.SEARCH_BACKEND == "searxng"
        assert cfg.AGENT_MAX_PLAN_STEPS == 5
        assert cfg.AGENT_MAX_RETRY == 2
        assert cfg.AGENT_TOOL_TIMEOUT == 15
        assert cfg.MAX_RESPONSE_TOKENS == 1024

    def test_superusers_parsing(self, monkeypatch):
        monkeypatch.setenv("SUPERUSERS", '["111","222"]')
        cfg = Config()
        cfg.__dict__.pop("SUPERUSERS", None)  # clear cached_property cache
        assert cfg.SUPERUSERS == ["111", "222"]

    def test_cache_hit(self):
        cfg1 = Config()
        cfg2 = Config()
        assert cfg1 is cfg2
