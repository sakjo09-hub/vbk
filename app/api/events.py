from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Event, Market, Selection, User
from app.schemas import EventOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
async def list_events(
    sport: str | None = Query(default=None, description="football / dota"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    stmt = (
        select(Event)
        .options(selectinload(Event.markets).selectinload(Market.selections))
        .where(Event.starts_at >= now)
        .where(Event.status.in_(["upcoming", "live"]))
        .order_by(Event.starts_at.asc())
        .limit(limit)
    )
    if sport:
        stmt = stmt.where(Event.sport == sport)
    if status_filter:
        stmt = stmt.where(Event.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(Event)
        .options(selectinload(Event.markets).selectinload(Market.selections))
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    return event
