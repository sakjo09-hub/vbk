"""Сидинг тестовых данных: создаёт таблицы, импортирует mock-события,
создаёт demo-пользователя. Безопасно перезапускать (upsert).

Запуск:  python -m scripts.seed_mock
"""
import asyncio

from sqlalchemy import select

from app.database import async_session_factory, create_all_tables
from app.models import Event, Market, Selection
from app.providers.registry import all_providers
from app.services.auth import get_user_by_email, register_user
from app.services.sync import sync_upcoming

DEMO_EMAIL = "demo@example.com"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


async def seed() -> None:
    await create_all_tables()

    async with async_session_factory() as db:
        for provider in all_providers():
            raw_events = await provider.fetch_upcoming()
            upserted = await sync_upcoming(db, raw_events, provider.name, provider.sport)
            print(f"[{provider.name}] импортировано событий: {upserted}")

        user = await get_user_by_email(db, DEMO_EMAIL)
        if user:
            print(f"\nDemo-пользователь уже существует: {DEMO_EMAIL} (баланс {user.balance})")
        else:
            user = await register_user(db, DEMO_USERNAME, DEMO_EMAIL, DEMO_PASSWORD)
            print(f"\nСоздан demo-пользователь:")
            print(f"  email:    {DEMO_EMAIL}")
            print(f"  пароль:   {DEMO_PASSWORD}")
            print(f"  баланс:   {user.balance} VC")

        result = await db.execute(
            select(Event).order_by(Event.sport, Event.starts_at)
        )
        events = list(result.scalars().all())
        print(f"\nСобытия в БД ({len(events)}):")
        for ev in events:
            mkts = await db.execute(select(Market).where(Market.event_id == ev.id))
            market = mkts.scalars().first()
            sels = await db.execute(select(Selection).where(Selection.market_id == market.id))
            odds_str = " / ".join(f"{s.label}={s.odds}" for s in sels.scalars().all())
            print(f"  #{ev.id} [{ev.sport}] {ev.tournament or '—'} | {ev.home_team} vs {ev.away_team} | {ev.starts_at:%Y-%m-%d %H:%M} | {odds_str}")


if __name__ == "__main__":
    asyncio.run(seed())
