import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import async_session_factory
from app.providers.registry import all_providers
from app.services.settlement import list_finished_unsettled_events
from app.services.sync import apply_results, sync_upcoming

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def job_fetch_upcoming() -> None:
    async with async_session_factory() as db:
        for provider in all_providers():
            try:
                raw_events = await provider.fetch_upcoming()
                added = await sync_upcoming(db, raw_events, provider.name, provider.sport)
                logger.info("provider=%s fetched=%s upserted=%s", provider.name, len(raw_events), added)
            except Exception as e:
                logger.warning("fetch_upcoming provider=%s error=%s", provider.name, e)


async def job_settle_events() -> None:
    async with async_session_factory() as db:
        for provider in all_providers():
            try:
                events = await list_finished_unsettled_events(settings.SETTLE_GRACE_MINUTES)
                pids = [e.provider_event_id for e in events if e.provider == provider.name]
                if not pids:
                    continue
                raw_results = await provider.fetch_results(pids)
                settled = await apply_results(db, raw_results, provider.name)
                logger.info("provider=%s settled_bets=%s", provider.name, settled)
            except Exception as e:
                logger.warning("settle_events provider=%s error=%s", provider.name, e)


def start_scheduler() -> None:
    scheduler.add_job(
        job_fetch_upcoming,
        "interval",
        minutes=settings.SCHEDULER_FETCH_INTERVAL_MINUTES,
        id="fetch_upcoming",
        replace_existing=True,
    )
    scheduler.add_job(
        job_settle_events,
        "interval",
        minutes=settings.SCHEDULER_SETTLE_INTERVAL_MINUTES,
        id="settle_events",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
