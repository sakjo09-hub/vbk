"""Парсер матчей Dota 2.

Аналогично футболу: реализуйте селекторы под целевой сайт БК.
Рынок 'match_winner' с исходами home/away (bo1/bo3 без ничьей),
опционально рынок 'map_winner' и тоталы карт.
"""
from app.providers.base import RawResult
from app.providers.parser import HttpParserProvider


class DotaParserProvider(HttpParserProvider):
    sport = "dota"
    name = "dota_parser"
    LISTING_URL = ""
    RESULTS_URL_TEMPLATE = ""

    def _parse_events_html(self, html: str):
        soup = self._soup(html)
        _ = soup
        return []

    def _parse_results_html(self, html: str, provider_event_id: str) -> list[RawResult]:
        soup = self._soup(html)
        _ = soup
        return [RawResult(provider_event_id=provider_event_id, status="finished", winning_outcome=None)]
