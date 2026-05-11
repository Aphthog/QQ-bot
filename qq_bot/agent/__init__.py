"""QQ Bot Agent Package.

Agent loop and supporting data classes for ReAct-style LLM interactions.
"""

from .response import ChatResponse, ToolCall

try:
    from .runner import run
except ImportError:
    # runner is created in a later task; expose once available
    def run() -> None:  # type: ignore[misc]
        raise NotImplementedError("Agent runner not yet implemented (Task 6)")

__all__ = ["run", "ChatResponse", "ToolCall"]
