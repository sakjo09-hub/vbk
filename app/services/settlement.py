from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bet, Event, Market, Selection, User
from app.services import wallet


async def settle_event(db: AsyncSession, event_id: int, winning_outcome: str | None) -> int:
    """Закрывает событие и рассчитывает все связанные ставки.

    winning_outcome — строка исхода, победившего в рынке 'match_winner'
    (например 'home' / 'away' / 'draw'). Если None — ставки возвращаются.
    Возвращает количество рассчитанных ставок.
    """
    event = await db.get(Event, event_id)
    if not event:
        return 0
    if event.status == "finished":
        return 0

    event.status = "finished"
    event.result = winning_outcome or "void"
    event.settled_at = datetime.now(timezone.utc)

    markets = await db.execute(select(Market).where(Market.event_id == event.id))
    settled = 0

    for market in markets.scalars().all():
        selections = await db.execute(select(Selection).where(Selection.market_id == market.id))
        for selection in selections.scalars().all():
            is_winner = (
                winning_outcome is not None
                and selection.outcome == winning_outcome
                and market.key == "match_winner"
            )
            selection.status = "won" if is_winner else ("lost" if winning_outcome else "void")

            bets = await db.execute(select(Bet).where(Bet.selection_id == selection.id, Bet.status == "pending"))
            for bet in bets.scalars().all():
                user = await db.get(User, bet.user_id)
                if is_winner:
                    bet.status = "won"
                    bet.payout = bet.potential_payout
                    await wallet.credit(db, user, bet.potential_payout, tx_type="payout", reference=f"bet:{bet.id}")
                elif winning_outcome is None:
                    bet.status = "cancelled"
                    bet.payout = bet.amount
                    await wallet.credit(db, user, bet.amount, tx_type="refund", reference=f"bet:{bet.id}")
                else:
                    bet.status = "lost"
                    bet.payout = Decimal("0")
                bet.settled_at = datetime.now(timezone.utc)
                settled += 1

    await db.commit()
    return settled


async def list_finished_unsettled_events(db: AsyncSession, grace_minutes: int = 0) -> list[Event]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=grace_minutes)
    result = await db.execute(
        select(Event)
        .where(Event.status.in_(["upcoming", "live"]))
        .where(Event.starts_at < cutoff)
    )
    return list(result.scalars().all())
