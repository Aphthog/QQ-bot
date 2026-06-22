import pytest
from qq_bot.agent.reflector import Reflector, REFLECTOR_SYSTEM_PROMPT
from qq_bot.agent.state import ReflectResult


class TestReflector:
    def test_system_prompt_not_empty(self):
        assert len(REFLECTOR_SYSTEM_PROMPT) > 0

    def test_parse_done(self):
        assert Reflector._parse("done") == ReflectResult.DONE
        assert Reflector._parse("DONE") == ReflectResult.DONE

    def test_parse_retry(self):
        assert Reflector._parse("retry") == ReflectResult.RETRY

    def test_parse_replan(self):
        assert Reflector._parse("replan") == ReflectResult.REPLAN

    def test_parse_unknown_defaults_to_done(self):
        assert Reflector._parse("garbage") == ReflectResult.DONE

    def test_parse_empty(self):
        assert Reflector._parse("") == ReflectResult.DONE
