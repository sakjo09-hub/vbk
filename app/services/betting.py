from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bet, Event, Market, Selection
from app.services import wallet


class BettingError(Exception):
    pass


async def place_bet(db: AsyncSession, user, selection_id: int, amount: Decimal) -> Bet:
    selection = await db.get(Selection, selection_id)
    if not selection:
        raise BettingError("Исход не найден")
    if selection.status != "open":
        raise BettingError("Ставки на этот исход закрыты")

    market = await db.get(Market, selection.market_id)
    event = await db.get(Event, market.event_id)
    now = datetime.now(timezone.utc)

    if event.status not in ("upcoming", "live"):
        raise BettingError("Событие недоступно для ставок")
    if event.starts_at < now and event.status == "upcoming":
        raise BettingError("Событие уже началось")

    tx = await wallet.debit(db, user, amount, reference=f"selection:{selection_id}")

    odds_snapshot = selection.odds
    potential_payout = (amount * odds_snapshot).quantize(Decimal("0.01"))

    bet = Bet(
        user_id=user.id,
        selection_id=selection_id,
        amount=amount,
        odds=odds_snapshot,
        status="pending",
        potential_payout=potential_payout,
    )
    db.add(bet)
    await db.flush()

    tx.reference = f"bet:{bet.id}"
    await db.commit()
    await db.refresh(bet)
    return bet


async def list_user_bets(db: AsyncSession, user_id: int, limit: int = 100) -> list[Bet]:
    result = await db.execute(
        select(Bet)
        .where(Bet.user_id == user_id)
        .order_by(Bet.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
