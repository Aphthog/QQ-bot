from .base import BaseSource
from .news import NewsSource
from .weather import WeatherSource
from .custom import CustomSource


def get_source(name: str) -> BaseSource | None:
    sources = {
        "news": NewsSource(),
        "weather": WeatherSource(),
        "custom": CustomSource(),
    }
    return sources.get(name)
