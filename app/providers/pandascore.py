import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.config import settings
from app.providers.base import BaseProvider, RawEvent, RawMarket, RawResult, RawSelection

logger = logging.getLogger(__name__)

PANDA_BASE = "https://api.pandascore.co"

GAME_SLUGS = {
    "dota": "dota2",
    "lol": "lol",
    "csgo": "csgo",
}


def _stable_factor(team_name: str, match_id: int) -> float:
    seed = int(hashlib.md5(f"{team_name}:{match_id}".encode()).hexdigest()[:8], 16)
    return 0.85 + (seed % 400) / 1000.0


def _generate_odds(home: str, away: str, match_id: int) -> tuple[Decimal, Decimal]:
    home_f = _stable_factor(home, match_id)
    away_f = _stable_factor(away, match_id)
    total = home_f + away_f
    margin = 1.06
    home_odds = max(1.10, round(1 / ((home_f / total) * margin), 2))
    away_odds = max(1.10, round(1 / ((away_f / total) * margin), 2))
    return Decimal(str(home_odds)), Decimal(str(away_odds))


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class PandascoreProvider(BaseProvider):
    def __init__(self, sport: str):
        self.sport = sport
        self.name = f"pandascore_{sport}"
        self._game = GAME_SLUGS.get(sport, sport)

    async def _get(self, path: str, params: dict | None = None) -> list | None:
        if not settings.PANDASCORE_API_KEY:
            logger.warning("PANDASCORE_API_KEY не задан — провайдер %s отключён", self.name)
            return None
        headers = {
            "Authorization": f"Bearer {settings.PANDASCORE_API_KEY}",
            "Accept": "application/json",
        }
        url = f"{PANDA_BASE}{path}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params or {}, headers=headers)
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining:
                logger.info("[%s] PandaScore квота: осталось %s", self.name, remaining)
            if resp.status_code == 429:
                logger.warning("[%s] превышен лимит PandaScore (429)", self.name)
                return None
            resp.raise_for_status()
            return resp.json()

    async def fetch_upcoming(self) -> list[RawEvent]:
        data = await self._get(f"/{self._game}/matches/upcoming", {"per_page": 30})
        if not data:
            return []
        events: list[RawEvent] = []
        for match in data:
            mapped = self._map_match(match)
            if mapped:
                events.append(mapped)
        return events

    def _map_match(self, match: dict) -> RawEvent | None:
        begin_at = match.get("begin_at")
        if not begin_at:
            return None
        try:
            starts_at = _parse_iso(begin_at)
        except (ValueError, TypeError):
            return None

        opponents = match.get("opponents", [])
        if len(opponents) < 2:
            return None

        home = opponents[0].get("opponent", {}).get("name", "Team A")
        away = opponents[1].get("opponent", {}).get("name", "Team B")

        league = match.get("league") or {}
        tournament = league.get("name") or ""
        if not tournament:
            serie = match.get("serie") or {}
            tournament = serie.get("full_name") or ""

        match_id = match["id"]
        home_odds, away_odds = _generate_odds(home, away, match_id)

        selections = [
            RawSelection("home", f"П1 {home}", home_odds),
            RawSelection("away", f"П2 {away}", away_odds),
        ]
        market = RawMarket("match_winner", "Победитель матча", selections)

        return RawEvent(
            provider_event_id=str(match_id),
            home_team=home,
            away_team=away,
            starts_at=starts_at,
            markets=[market],
            source_url=None,
            tournament=tournament or "Dota 2",
        )

    async def fetch_results(self, provider_event_ids: list[str]) -> list[RawResult]:
        if not settings.PANDASCORE_API_KEY or not provider_event_ids:
            return []

        pid_set = set(provider_event_ids)
        results: list[RawResult] = []
        page = 1

        while True:
            data = await self._get(f"/{self._game}/matches/past", {
                "per_page": 50,
                "page": page,
            })
            if not data:
                break

            for match in data:
                match_id = str(match.get("id"))
                if match_id not in pid_set:
                    continue
                outcome = self._winner(match)
                if outcome:
                    results.append(RawResult(
                        provider_event_id=match_id,
                        status="finished",
                        winning_outcome=outcome,
                    ))
                    pid_set.discard(match_id)

            if not pid_set or len(data) < 50:
                break
            page += 1

        return results

    @staticmethod
    def _winner(match: dict) -> str | None:
        winner_id = match.get("winner_id")
        if not winner_id:
            return None
        opponents = match.get("opponents", [])
        if len(opponents) < 2:
            return None
        if winner_id == opponents[0].get("opponent", {}).get("id"):
            return "home"
        if winner_id == opponents[1].get("opponent", {}).get("id"):
            return "away"
        return None
