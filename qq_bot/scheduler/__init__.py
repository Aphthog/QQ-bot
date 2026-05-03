from qq_bot.scheduler.base import BaseSource
from qq_bot.scheduler.news import NewsSource
from qq_bot.scheduler.weather import WeatherSource
from qq_bot.scheduler.custom import CustomSource

_sources = {
    "news": NewsSource(),
    "weather": WeatherSource(),
    "custom": CustomSource(),
}


def get_source(name: str) -> BaseSource | None:
    return _sources.get(name)


def list_sources() -> list[str]:
    return list(_sources.keys())
