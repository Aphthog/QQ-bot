import pytest
from qq_bot.tools.registry import ToolRegistry, tool


class TestToolRegistry:
    def setup_method(self):
        ToolRegistry._tools.clear()

    @pytest.mark.asyncio
    async def test_decorator_registers_tool(self):
        @tool(name="greet", description="Say hello", params={"name": (str, "who to greet")})
        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        assert "greet" in ToolRegistry._tools
        result = await ToolRegistry.execute("greet", {"name": "World"}, ctx={})
        assert result == "Hello, World!"

    def test_decorator_generates_schema(self):
        @tool(
            name="search",
            description="Search the web",
            params={"query": (str, "search keywords"), "limit": (int, "max results")},
            category="core",
            require_auth=False,
        )
        async def search(query: str, limit: int = 5) -> str:
            return f"search: {query}"

        schema = ToolRegistry.get_schema("search")
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "query" in schema["function"]["parameters"]["properties"]
        assert "limit" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["query"]

    def test_get_all_schemas(self):
        @tool(name="a", description="A", params={})
        async def a() -> str: return "a"

        @tool(name="b", description="B", params={}, category="admin")
        async def b() -> str: return "b"

        all_schemas = ToolRegistry.get_all_schemas()
        assert len(all_schemas) == 2

        user_schemas = ToolRegistry.get_all_schemas(for_user=True)
        assert len(user_schemas) == 1  # a only, b is admin

    def test_tool_not_found(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            ToolRegistry.get_schema("nonexistent")

    def test_duplicate_registration(self):
        @tool(name="dup", description="First", params={})
        async def dup1() -> str: return "1"

        with pytest.raises(ValueError, match="already registered"):
            @tool(name="dup", description="Second", params={})
            async def dup2() -> str: return "2"
