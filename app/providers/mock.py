import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.providers.base import BaseProvider, RawEvent, RawMarket, RawResult, RawSelection

FOOTBALL_TEAMS = [
    "Manchester City", "Arsenal", "Liverpool", "Chelsea",
    "Tottenham", "Real Madrid", "Barcelona", "Atletico",
    "Bayern", "Dortmund", "PSG", "Juventus",
    "Inter", "Milan", "Napoli", "Atalanta",
]

DOTA_TEAMS = [
    "Team Spirit", "Gaimin Gladiators", "Team Liquid", "Tundra",
    "OG", "Team Secret", "BetBoom", "Virtus.pro",
    "Natus Vincere", "Entity", "PSG.LGD", "Xtreme Gaming",
]

START_OFFSETS_HOURS = [1, 2, 3, 5, 8, 12, 24, 30, 40, 44]


def _round_odds(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


class MockProvider(BaseProvider):
    def __init__(self, sport: str):
        self.sport = sport
        self.name = f"mock_{sport}"
        self._teams = FOOTBALL_TEAMS if sport == "football" else DOTA_TEAMS

    def _pairs(self) -> list[tuple[str, str]]:
        teams = self._teams
        return [(teams[i], teams[i + 1]) for i in range(0, len(teams) - 1, 2)]

    async def fetch_upcoming(self) -> list[RawEvent]:
        now = datetime.now(timezone.utc)
        events: list[RawEvent] = []
        for idx, (home, away) in enumerate(self._pairs()):
            offset = START_OFFSETS_HOURS[idx % len(START_OFFSETS_HOURS)]
            starts_at = (now + timedelta(hours=offset)).replace(minute=0, second=0, microsecond=0)
            events.append(self._build_event(home, away, starts_at, idx))
        return events

    def _build_event(self, home: str, away: str, starts_at: datetime, idx: int) -> RawEvent:
        rnd = random.Random(f"{self.sport}-{home}-{away}-{idx}")
        if self.sport == "football":
            selections = [
                RawSelection("home", f"П1 {home}", _round_odds(rnd.uniform(1.4, 3.2))),
                RawSelection("draw", "Ничья", _round_odds(rnd.uniform(2.8, 4.5))),
                RawSelection("away", f"П2 {away}", _round_odds(rnd.uniform(1.4, 3.2))),
            ]
        else:
            selections = [
                RawSelection("home", f"П1 {home}", _round_odds(rnd.uniform(1.3, 3.0))),
                RawSelection("away", f"П2 {away}", _round_odds(rnd.uniform(1.3, 3.0))),
            ]
        market = RawMarket("match_winner", "Победитель матча", selections)
        pid = f"mock-{self.sport}-{idx + 1}"
        tournament = "Демо: Dota Pro Circuit" if self.sport == "dota" else "Демо: Премьер-лига"
        return RawEvent(
            provider_event_id=pid,
            home_team=home,
            away_team=away,
            starts_at=starts_at,
            markets=[market],
            source_url=None,
            tournament=tournament,
        )

    async def fetch_results(self, provider_event_ids: list[str]) -> list[RawResult]:
        results: list[RawResult] = []
        for pid in provider_event_ids:
            sport = "football" if pid.startswith("mock-football") else "dota"
            outcomes = ["home", "draw", "away"] if sport == "football" else ["home", "away"]
            winner = random.choice(outcomes)
            results.append(RawResult(provider_event_id=pid, status="finished", winning_outcome=winner))
        return results
