from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Market, Selection
from app.providers.base import RawEvent, RawResult


async def upsert_event(db: AsyncSession, raw: RawEvent, provider_name: str, sport: str) -> Event:
    result = await db.execute(
        select(Event).where(
            Event.provider == provider_name,
            Event.provider_event_id == raw.provider_event_id,
        )
    )
    event = result.scalar_one_or_none()

    if event is None:
        event = Event(
            sport=sport,
            provider=provider_name,
            provider_event_id=raw.provider_event_id,
            tournament=raw.tournament,
            home_team=raw.home_team,
            away_team=raw.away_team,
            starts_at=raw.starts_at,
            source_url=raw.source_url,
            status="upcoming",
        )
        db.add(event)
        await db.flush()
    else:
        event.home_team = raw.home_team
        event.away_team = raw.away_team
        event.starts_at = raw.starts_at
        if raw.tournament:
            event.tournament = raw.tournament
        if raw.source_url:
            event.source_url = raw.source_url

    markets_result = await db.execute(select(Market).where(Market.event_id == event.id))
    existing_markets = {m.key: m for m in markets_result.scalars().all()}

    for raw_market in raw.markets:
        market = existing_markets.get(raw_market.key)
        if market is None:
            market = Market(event_id=event.id, key=raw_market.key, label=raw_market.label)
            db.add(market)
            await db.flush()
        else:
            market.label = raw_market.label

        selections_result = await db.execute(select(Selection).where(Selection.market_id == market.id))
        existing_selections = {s.outcome: s for s in selections_result.scalars().all()}

        for raw_sel in raw_market.selections:
            selection = existing_selections.get(raw_sel.outcome)
            if selection is None:
                selection = Selection(
                    market_id=market.id,
                    outcome=raw_sel.outcome,
                    label=raw_sel.label,
                    odds=raw_sel.odds,
                    status="open",
                )
                db.add(selection)
            else:
                selection.label = raw_sel.label
                if selection.status == "open":
                    selection.odds = raw_sel.odds

    await db.flush()
    return event


async def sync_upcoming(db: AsyncSession, raw_events: list[RawEvent], provider_name: str, sport: str) -> int:
    count = 0
    for raw in raw_events:
        try:
            await upsert_event(db, raw, provider_name, sport)
            count += 1
        except Exception:
            continue
    await db.commit()
    return count


async def apply_results(db: AsyncSession, raw_results: list[RawResult], provider_name: str) -> int:
    from app.services.settlement import settle_event

    settled = 0
    for raw in raw_results:
        result = await db.execute(
            select(Event).where(
                Event.provider == provider_name,
                Event.provider_event_id == raw.provider_event_id,
            )
        )
        event = result.scalar_one_or_none()
        if not event or event.status == "finished":
            continue
        if raw.status == "finished":
            settled += await settle_event(db, event.id, raw.winning_outcome)
        elif raw.status == "live" and event.status == "upcoming":
            event.status = "live"
            await db.commit()
    return settled
