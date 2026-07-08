import asyncio
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, select

from app.api import admin, auth, bets, events, wallet
from app.config import settings
from app.database import async_session_factory
from app.models import Bet, Event, Market, Selection
from app.providers.registry import get_provider
from app.workers.scheduler import job_fetch_upcoming, start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(
    title="Virtual Betting API",
    description="Букмекерская платформа на виртуальной валюте для тренировки спортивной аналитики.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await _cleanup_mock_events()
    start_scheduler()
    asyncio.create_task(_initial_fetch_if_empty())


async def _cleanup_mock_events() -> None:
    """Удаляет все mock-события если активен реальный провайдер."""
    log = logging.getLogger(__name__)
    try:
        async with async_session_factory() as db:
            for sport in ("football", "dota"):
                provider = get_provider(sport)
                if provider is None or provider.name.startswith("mock_"):
                    continue
                mock_key = f"mock_{sport}"
                mock_ids = (await db.execute(
                    select(Event.id).where(Event.provider == mock_key)
                )).scalars().all()
                if not mock_ids:
                    log.info("mock_%s: событий нет, пропускаем", sport)
                    continue
                log.info("mock_%s: найдено %s событий для удаления", sport, len(mock_ids))
                market_ids = (await db.execute(
                    select(Market.id).where(Market.event_id.in_(mock_ids))
                )).scalars().all()
                if market_ids:
                    await db.execute(
                        delete(Bet).where(Bet.selection_id.in_(
                            select(Selection.id).where(Selection.market_id.in_(market_ids))
                        ))
                    )
                await db.execute(delete(Event).where(Event.id.in_(mock_ids)))
                await db.commit()
                log.info("mock_%s: удалено %s событий", sport, len(mock_ids))
    except Exception as e:
        log.error("cleanup mock events failed: %s", e, exc_info=True)


async def _initial_fetch_if_empty() -> None:
    """При первом запуске (или если сменился провайдер спорта)
    сразу импортирует события, чтобы сайт не был пустым."""
    await asyncio.sleep(3)
    try:
        async with async_session_factory() as db:
            for sport in ("football", "dota"):
                provider = get_provider(sport)
                if provider is None:
                    continue
                count = (await db.execute(
                    select(func.count()).select_from(Event).where(
                        Event.sport == sport,
                        Event.provider == provider.name,
                    )
                )).scalar()
                if not count:
                    await job_fetch_upcoming()
                    return
    except Exception as e:
        logging.getLogger(__name__).warning("initial fetch failed: %s", e)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_scheduler()


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "currency": settings.VIRTUAL_CURRENCY_CODE}


app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(bets.router, prefix="/api")
app.include_router(wallet.router, prefix="/api")
app.include_router(admin.router)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str, request: Request):
        index = os.path.join(STATIC_DIR, "index.html")
        return FileResponse(index)
