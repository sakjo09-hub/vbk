from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class RawSelection:
    outcome: str
    label: str
    odds: Decimal


@dataclass
class RawMarket:
    key: str
    label: str
    selections: list[RawSelection] = field(default_factory=list)


@dataclass
class RawEvent:
    provider_event_id: str
    home_team: str
    away_team: str
    starts_at: datetime
    markets: list[RawMarket] = field(default_factory=list)
    source_url: str | None = None
    tournament: str = ""


@dataclass
class RawResult:
    provider_event_id: str
    status: str
    winning_outcome: str | None = None


class BaseProvider(ABC):
    sport: str = ""
    name: str = ""

    @abstractmethod
    async def fetch_upcoming(self) -> list[RawEvent]:
        ...

    @abstractmethod
    async def fetch_results(self, provider_event_ids: list[str]) -> list[RawResult]:
        ...
