try:
    from .runner import run  # noqa: F401
except ImportError:
    # runner.py 将在 Task 6 创建
    async def run(*args, **kwargs):
        raise NotImplementedError("Agent runner not yet implemented")

__all__ = ["run"]
