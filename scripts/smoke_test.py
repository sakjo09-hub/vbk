"""Smoke-тест полного цикла без HTTP: создаёт данные, ставит, рассчитывает,
проверяет выплату. Запуск:  python -m scripts.smoke_test
"""
import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.database import async_session_factory, create_all_tables
from app.models import Event, Market, Selection, User
from app.providers.registry import get_provider
from app.services.auth import get_user_by_email, register_user
from app.services.betting import list_user_bets, place_bet
from app.services.sync import sync_upcoming
from app.services.wallet import credit, list_transactions

DEMO_EMAIL = "smoke@example.com"


async def main() -> None:
    await create_all_tables()

    async with async_session_factory() as db:
        provider = get_provider("football")
        raw_events = await provider.fetch_upcoming()
        await sync_upcoming(db, raw_events, provider.name, provider.sport)

        event = (await db.execute(select(Event).where(Event.sport == "football").order_by(Event.starts_at))).scalars().first()
        market = (await db.execute(select(Market).where(Market.event_id == event.id))).scalars().first()
        home_sel = (await db.execute(select(Selection).where(Selection.market_id == market.id, Selection.outcome == "home"))).scalars().first()
        print(f"Событие: #{event.id} {event.home_team} vs {event.away_team}")
        print(f"Исход home: id={home_sel.id} odds={home_sel.odds}")

        user = await get_user_by_email(db, DEMO_EMAIL)
        if not user:
            user = await register_user(db, "smoke", DEMO_EMAIL, "smoke123")
        print(f"Пользователь: {user.email} баланс={user.balance}")

        bet_amount = Decimal("1000")
        bet = await place_bet(db, user, home_sel.id, bet_amount)
        await db.refresh(user)
        print(f"Ставка: #{bet.id} amount={bet.amount} odds={bet.odds} потенциальная выплата={bet.potential_payout}")
        print(f"Баланс после ставки: {user.balance} (ожидаемо {Decimal('10000') - bet_amount})")
        assert user.balance == Decimal("10000") - bet_amount, "Баланс не списан корректно"

        from app.services.settlement import settle_event
        settled = await settle_event(db, event.id, "home")
        await db.refresh(user)
        await db.refresh(bet)
        bets = await list_user_bets(db, user.id)
        print(f"Расчёт (победа home): ставок рассчитано={settled}")
        print(f"Ставка статус={bet.status} выплата={bet.payout}")
        print(f"Баланс после выигрыша: {user.balance} (ожидаемо {Decimal('10000') - bet_amount + bet.potential_payout})")
        assert bet.status == "won", "Ставка должна быть выиграна"
        assert user.balance == Decimal("10000") - bet_amount + bet.potential_payout, "Выплата некорректна"

        txs = await list_transactions(db, user.id)
        print(f"Транзакций: {len(txs)}")
        for tx in txs:
            print(f"  {tx.type} amount={tx.amount} balance_after={tx.balance_after}")

    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
