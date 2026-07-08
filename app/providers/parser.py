"""Базовый HTML-парсер страниц букмекерских контор.

ВНИМАНИЕ: парсинг конкретных БК зависит от их верстки и часто меняется,
а также может противоречить их ToS. Этот класс даёт каркас: переопределите
LISTING_URL и методы _parse_events_html / _parse_results_html под целевой сайт.
Альтернатива — заменить парсер на публичное API (TheSportsDB, OpenDota),
реализовав тот же интерфейс BaseProvider.
"""
from __future__ import annotations

from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from app.providers.base import BaseProvider, RawEvent, RawResult


class HttpParserProvider(BaseProvider):
    LISTING_URL: str = ""
    RESULTS_URL_TEMPLATE: str = ""
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    )
    REQUEST_TIMEOUT: float = 20.0

    async def _fetch_html(self, url: str) -> str:
        headers = {"User-Agent": self.USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"}
        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    @staticmethod
    def _parse_odds(text: str) -> Decimal | None:
        cleaned = text.replace(",", ".").strip()
        try:
            return Decimal(cleaned)
        except Exception:
            return None

    async def fetch_upcoming(self) -> list[RawEvent]:
        if not self.LISTING_URL:
            return []
        html = await self._fetch_html(self.LISTING_URL)
        return self._parse_events_html(html)

    async def fetch_results(self, provider_event_ids: list[str]) -> list[RawResult]:
        if not self.RESULTS_URL_TEMPLATE:
            return []
        results: list[RawResult] = []
        for pid in provider_event_ids:
            url = self.RESULTS_URL_TEMPLATE.format(provider_event_id=pid)
            try:
                html = await self._fetch_html(url)
            except httpx.HTTPError:
                continue
            results.extend(self._parse_results_html(html, pid))
        return results

    def _parse_events_html(self, html: str) -> list[RawEvent]:
        raise NotImplementedError

    def _parse_results_html(self, html: str, provider_event_id: str) -> list[RawResult]:
        raise NotImplementedError
