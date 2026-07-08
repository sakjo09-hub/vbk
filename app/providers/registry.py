from app.config import settings
from app.providers.base import BaseProvider
from app.providers.dota import DotaParserProvider
from app.providers.football import FootballParserProvider
from app.providers.mock import MockProvider
from app.providers.odds_api import OddsApiProvider


def get_provider(sport: str) -> BaseProvider | None:
    sport = sport.lower()
    if sport == "football":
        choice = settings.FOOTBALL_PROVIDER
    elif sport == "dota":
        choice = settings.DOTA_PROVIDER
    else:
        return None
    if choice == "mock":
        return MockProvider(sport)
    if choice == "odds_api":
        return OddsApiProvider(sport)
    if sport == "football":
        return FootballParserProvider()
    if sport == "dota":
        return DotaParserProvider()
    return None


def all_providers() -> list[BaseProvider]:
    providers: list[BaseProvider] = []
    for sport in ("football", "dota"):
        p = get_provider(sport)
        if p:
            providers.append(p)
    return providers
