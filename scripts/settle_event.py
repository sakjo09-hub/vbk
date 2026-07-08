"""Ручной расчёт события для быстрого теста выплаты.

Запуск:
  python -m scripts.settle_event <event_id> <winning_outcome>
  winning_outcome: home | draw | away | void

Пример:
  python -m scripts.settle_event 3 home
"""
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Bet, Event, Market, Selection
from app.services.settlement import settle_event

VALID_OUTCOMES = {"home", "draw", "away", "void"}


async def main(event_id: int, outcome: str) -> None:
    winning = None if outcome == "void" else outcome
    async with async_session_factory() as db:
        event = await db.get(Event, event_id)
        if not event:
            print(f"Событие #{event_id} не найдено")
            return
        print(f"Расчёт: #{event.id} {event.home_team} vs {event.away_team} -> победитель: {outcome}")

        settled = await settle_event(db, event_id, winning)
        print(f"Рассчитано ставок: {settled}")

        bets = await db.execute(
            select(Bet)
            .join(Selection, Bet.selection_id == Selection.id)
            .join(Market, Selection.market_id == Market.id)
            .where(Market.event_id == event_id)
        )
        for bet in bets.scalars().all():
            print(f"  bet #{bet.id} user={bet.user_id} amount={bet.amount} odds={bet.odds} -> {bet.status} payout={bet.payout}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python -m scripts.settle_event <event_id> <home|draw|away|void>")
        sys.exit(1)
    try:
        eid = int(sys.argv[1])
    except ValueError:
        print("event_id должен быть числом")
        sys.exit(1)
    if sys.argv[2] not in VALID_OUTCOMES:
        print(f"outcome должен быть одним из: {VALID_OUTCOMES}")
        sys.exit(1)
    asyncio.run(main(eid, sys.argv[2]))
