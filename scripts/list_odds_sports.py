"""Показывает доступные виды спорта в The Odds API (бесплатно, без расхода квоты).

Запуск:  python -m scripts.list_odds_sports
Сначала задайте ODDS_API_KEY в .env.
"""
import asyncio

import httpx

from app.config import settings


async def main() -> None:
    if not settings.ODDS_API_KEY:
        print("Сначала задайте ODDS_API_KEY в .env")
        return

    url = f"{settings.ODDS_API_BASE}/sports/"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, params={"apiKey": settings.ODDS_API_KEY})
        if resp.status_code != 200:
            print(f"Ошибка {resp.status_code}: {resp.text}")
            return
        sports = resp.json()

    print("Доступные виды спорта (active=true):\n")
    print(f"{'ключ':45} {'группа':22} {'название'}")
    print("-" * 90)
    for s in sports:
        if s.get("active"):
            print(f"{s['key']:45} {s.get('group',''):22} {s.get('title','')}")

    print(f"\nКвота: осталось={resp.headers.get('x-requests-remaining')} "
          f"использовано={resp.headers.get('x-requests-used')}")
    print("\nПодходящие для футбола ключи начинаются с 'soccer_'.")
    print("Для киберспорта ищите 'lol', 'cs_go', 'dota2' и т.п. (покрытие зависит от сезона/тарифа).")
    print("Впишите нужные ключи в .env: ODDS_API_FOOTBALL_SPORTS / ODDS_API_DOTA_SPORTS.")


if __name__ == "__main__":
    asyncio.run(main())
