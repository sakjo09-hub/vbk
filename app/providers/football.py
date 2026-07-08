"""Парсер футбольных матчей.

Структура RawEvent возвращается в нормализованном виде. Реализуйте
_parse_events_html / _parse_results_html под целевой сайт БК:
- LISTING_URL — страница линии (футбол)
- для каждого матча извлеките команды, время начала, коэффициенты 1/X/2
- в markets кладём рынок 'match_winner' с исходами home/draw/away
"""
from datetime import datetime

from app.providers.base import RawEvent, RawMarket, RawResult, RawSelection
from app.providers.parser import HttpParserProvider


class FootballParserProvider(HttpParserProvider):
    sport = "football"
    name = "football_parser"
    LISTING_URL = ""  # пример: "https://example-bk.com/line/football"
    RESULTS_URL_TEMPLATE = ""  # пример: "https://example-bk.com/results/{provider_event_id}"

    def _parse_events_html(self, html: str) -> list[RawEvent]:
        soup = self._soup(html)
        events: list[RawEvent] = []

        # TODO: заполнить селекторами целевого сайта.
        # for node in soup.select(".event-row"):
        #     home = node.select_one(".team-home").get_text(strip=True)
        #     away = node.select_one(".team-away").get_text(strip=True)
        #     starts_at = datetime.fromisoformat(node["data-start"])
        #     odds_home = self._parse_odds(node.select_one(".odds-1").get_text())
        #     ...
        #     events.append(RawEvent(...))
        _ = soup
        return events

    def _parse_results_html(self, html: str, provider_event_id: str) -> list[RawResult]:
        soup = self._soup(html)
        # TODO: извлечь счёт и сопоставить с home/draw/away.
        _ = soup
        return [RawResult(provider_event_id=provider_event_id, status="finished", winning_outcome=None)]
