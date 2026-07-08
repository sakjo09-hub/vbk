import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.config import settings
from app.providers.base import BaseProvider, RawEvent, RawMarket, RawResult, RawSelection

logger = logging.getLogger(__name__)

_TOURNAMENT_TITLES = {
    "soccer_fifa_world_cup": "Чемпионат мира 2026",
    "soccer_epl": "Английская Премьер-лига",
    "soccer_spain_la_liga": "Ла Лига",
    "soccer_italy_serie_a": "Серия А",
    "soccer_germany_bundesliga": "Бундеслига",
    "soccer_france_ligue_one": "Лига 1",
    "soccer_uefa_champs_league": "Лига Чемпионов УЕФА",
    "soccer_uefa_champs_league_qualification": "ЛЧ: Квалификация",
    "soccer_uefa_europa_league": "Лига Европы УЕФА",
    "soccer_usa_mls": "MLS",
    "soccer_brazil_campeonato": "Бразилия: Серия А",
    "soccer_argentina_primera_division": "Аргентина: Примера",
    "soccer_efl_champ": "Чемпионшип",
    "soccer_norway_eliteserien": "Норвегия: Элитсерия",
    "soccer_sweden_allsvenskan": "Швеция: Аллсвенскан",
    "soccer_netherlands_eredivisie": "Эредивизи",
    "soccer_mexico_ligamx": "Лига MX",
}


def _tournament_title(sport_key: str, response_title: str | None) -> str:
    if sport_key in _TOURNAMENT_TITLES:
        return _TOURNAMENT_TITLES[sport_key]
    if response_title:
        return response_title
    return sport_key.replace("soccer_", "").replace("_", " ").title()


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class OddsApiProvider(BaseProvider):
    def __init__(self, sport: str):
        self.sport = sport
        self.name = f"odds_api_{sport}"
        raw = settings.ODDS_API_FOOTBALL_SPORTS if sport == "football" else settings.ODDS_API_DOTA_SPORTS
        self._sport_keys = [s.strip() for s in raw.split(",") if s.strip()]
        self._regions = settings.ODDS_API_REGIONS

    async def _get(self, path: str, params: dict) -> list | None:
        if not settings.ODDS_API_KEY:
            logger.warning("ODDS_API_KEY не задан — провайдер %s отключён", self.name)
            return None
        params = {**params, "apiKey": settings.ODDS_API_KEY}
        url = settings.ODDS_API_BASE + path
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params)
            remaining = resp.headers.get("x-requests-remaining")
            if remaining:
                logger.info("[%s] квота The Odds API: осталось %s (использовано %s)",
                            self.name, remaining, resp.headers.get("x-requests-used"))
            if resp.status_code == 429:
                logger.warning("[%s] превышен лимит The Odds API (429)", self.name)
                return None
            resp.raise_for_status()
            return resp.json()

    async def fetch_upcoming(self) -> list[RawEvent]:
        events: list[RawEvent] = []
        for sk in self._sport_keys:
            try:
                data = await self._get(f"/sports/{sk}/odds/", {
                    "regions": self._regions,
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                })
            except httpx.HTTPError as e:
                logger.warning("[%s] не удалось получить odds для %s: %s", self.name, sk, e)
                continue
            if not data:
                continue
            for ev in data:
                mapped = self._map_event(ev, sk)
                if mapped:
                    events.append(mapped)
        return events

    def _map_event(self, ev: dict, sport_key: str = "") -> RawEvent | None:
        try:
            starts_at = _parse_iso(ev["commence_time"])
        except (KeyError, ValueError):
            return None
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        outcomes = self._aggregate_h2h(ev.get("bookmakers", []), home, away)
        if not outcomes:
            return None
        selections = [
            RawSelection(code, self._label(code, home, away), Decimal(str(round(price, 2))))
            for code, price in outcomes.items()
        ]
        order = {"home": 0, "draw": 1, "away": 2}
        selections.sort(key=lambda s: order.get(s.outcome, 9))
        market = RawMarket("match_winner", "Победитель матча", selections)
        return RawEvent(
            provider_event_id=ev["id"],
            home_team=home,
            away_team=away,
            starts_at=starts_at,
            markets=[market],
            source_url=None,
            tournament=_tournament_title(sport_key, ev.get("sport_title")),
        )

    def _aggregate_h2h(self, bookmakers: list, home: str, away: str) -> dict:
        prices: dict[str, list[float]] = {}
        for bm in bookmakers:
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for o in market.get("outcomes", []):
                    code = self._outcome_code(o.get("name"), home, away)
                    if code:
                        try:
                            prices.setdefault(code, []).append(float(o.get("price")))
                        except (TypeError, ValueError):
                            continue
        return {code: sum(v) / len(v) for code, v in prices.items() if v}

    @staticmethod
    def _outcome_code(name: str | None, home: str, away: str) -> str | None:
        if name is None:
            return None
        if name == home:
            return "home"
        if name == away:
            return "away"
        if name.lower() == "draw":
            return "draw"
        return None

    @staticmethod
    def _label(code: str, home: str, away: str) -> str:
        if code == "home":
            return f"П1 {home}"
        if code == "away":
            return f"П2 {away}"
        return "Ничья"

    async def fetch_results(self, provider_event_ids: list[str]) -> list[RawResult]:
        if not settings.ODDS_API_KEY or not self._sport_keys or not provider_event_ids:
            return []
        results: list[RawResult] = []
        for sk in self._sport_keys:
            try:
                data = await self._get(f"/sports/{sk}/scores/", {
                    "daysFrom": 3,
                    "eventIds": ",".join(provider_event_ids),
                })
            except httpx.HTTPError as e:
                logger.warning("[%s] не удалось получить scores для %s: %s", self.name, sk, e)
                continue
            if not data:
                continue
            for ev in data:
                if not ev.get("completed"):
                    continue
                results.append(RawResult(
                    provider_event_id=ev["id"],
                    status="finished",
                    winning_outcome=self._winner(ev),
                ))
        return results

    @staticmethod
    def _winner(ev: dict) -> str | None:
        scores = ev.get("scores") or []
        score_map = {s.get("name"): s.get("score") for s in scores}
        try:
            h = float(score_map.get(ev.get("home_team")))
            a = float(score_map.get(ev.get("away_team")))
        except (TypeError, ValueError):
            return None
        if h > a:
            return "home"
        if a > h:
            return "away"
        return "draw"
