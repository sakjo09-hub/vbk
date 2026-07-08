import logging

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select

from app.api.deps import get_current_user
from app.config import settings
from app.database import async_session_factory
from app.models import Bet, Event, Market, Selection, User
from app.providers.pandascore import PandascoreProvider

router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger(__name__)


@router.get("/test-pandascore")
async def test_pandascore(_user: User = Depends(get_current_user)):
    provider = PandascoreProvider("dota")
    result = {
        "provider": provider.name,
        "game_slug": provider._game,
        "key_set": bool(settings.PANDASCORE_API_KEY),
        "key_prefix": settings.PANDASCORE_API_KEY[:8] + "..." if settings.PANDASCORE_API_KEY else "—",
    }

    raw = await provider._get(f"/{provider._game}/matches/upcoming", {"per_page": 5})
    if raw is None:
        result["error"] = "API key missing or rate limited"
        return result

    result["api_objects_count"] = len(raw)
    result["samples"] = []

    for match in raw[:3]:
        sample = {
            "id": match.get("id"),
            "name": match.get("name"),
            "begin_at": match.get("begin_at"),
            "status": match.get("status"),
            "opponents": [o.get("opponent", {}).get("name") for o in match.get("opponents", [])[:2]],
            "league": (match.get("league") or {}).get("name"),
            "serie": (match.get("serie") or {}).get("full_name"),
        }
        result["samples"].append(sample)
        mapped = provider._map_match(match)
        if mapped:
            result.setdefault("mapped_events", []).append({
                "home": mapped.home_team,
                "away": mapped.away_team,
                "starts_at": str(mapped.starts_at),
                "tournament": mapped.tournament,
                "provider_event_id": mapped.provider_event_id,
                "selections": [{"outcome": s.outcome, "label": s.label, "odds": float(s.odds)} for s in mapped.markets[0].selections] if mapped.markets else [],
            })

    return result


@router.post("/cleanup-mock")
async def cleanup_mock(_user: User = Depends(get_current_user)):
    """Удаляет все mock-события, на которые не было ставок."""
    async with async_session_factory() as db:
        result = {"sports": {}}
        for sport in ("football", "dota"):
            provider_key = f"mock_{sport}"
            mock_ids = (await db.execute(
                select(Event.id).where(Event.provider == provider_key)
            )).scalars().all()
            if not mock_ids:
                result["sports"][sport] = {"found": 0, "deleted": 0}
                continue

            bet_market_ids = (await db.execute(
                select(Selection.market_id).join(Bet).where(
                    Selection.market_id.in_(
                        select(Market.id).where(Market.event_id.in_(mock_ids))
                    )
                )
            )).scalars().all()
            bet_event_ids = set(
                (await db.execute(
                    select(Market.event_id).where(Market.id.in_(bet_market_ids))
                )).scalars().all()
            ) if bet_market_ids else set()

            safe_ids = [eid for eid in mock_ids if eid not in bet_event_ids]
            if safe_ids:
                await db.execute(
                    delete(Selection).where(Selection.market_id.in_(
                        select(Market.id).where(Market.event_id.in_(safe_ids))
                    ))
                )
                await db.execute(delete(Market).where(Market.event_id.in_(safe_ids)))
                await db.execute(delete(Event).where(Event.id.in_(safe_ids)))
                await db.commit()

            result["sports"][sport] = {
                "found": len(mock_ids),
                "with_bets": len(bet_event_ids),
                "deleted": len(safe_ids),
            }
        return result
