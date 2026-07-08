import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, bets, events, wallet
from app.config import settings
from app.workers.scheduler import start_scheduler, stop_scheduler

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
    start_scheduler()


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

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str, request: Request):
        index = os.path.join(STATIC_DIR, "index.html")
        return FileResponse(index)
