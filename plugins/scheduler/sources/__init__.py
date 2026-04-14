from .base import BaseSource
from .news import NewsSource
from .weather import WeatherSource
from .custom import CustomSource


_sources = {
    "news": NewsSource(),
    "weather": WeatherSource(),
    "custom": CustomSource(),
}


def get_source(name: str) -> BaseSource | None:
    return _sources.get(name)


def list_sources() -> list[str]:
    return list(_sources.keys())
