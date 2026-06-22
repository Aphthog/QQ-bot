import pytest
from qq_bot.tools.core import web_search, web_fetch, run_code


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_returns_string(self):
        result = await web_search(query="Python programming")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_empty_query(self):
        result = await web_search(query="")
        assert "[搜索失败" in result or "缺少" in result


class TestWebFetch:
    @pytest.mark.asyncio
    async def test_invalid_url(self):
        result = await web_fetch(url="not-a-url")
        assert "失败" in result or "无效" in result


class TestRunCode:
    @pytest.mark.asyncio
    async def test_simple_expression(self):
        result = await run_code(code="print(1+1)")
        assert "2" in result

    @pytest.mark.asyncio
    async def test_timeout(self):
        result = await run_code(code="import time; time.sleep(999)")
        assert "超时" in result or "timeout" in result

    @pytest.mark.asyncio
    async def test_forbidden_import(self):
        result = await run_code(code="import os; os.system('echo bad')")
        assert "禁止" in result or "forbidden" in result
