from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


def to_async_url(url: str) -> str:
    if "+asyncpg" in url or "+aiosqlite" in url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def to_sync_url(url: str) -> str:
    if "+psycopg2" in url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if "+aiosqlite" in url:
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    DATABASE_URL_SYNC: str = ""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    VIRTUAL_CURRENCY_CODE: str = "VC"
    VIRTUAL_STARTING_BALANCE: int = 10000

    FOOTBALL_PROVIDER: str = "parser"
    DOTA_PROVIDER: str = "parser"

    ODDS_API_KEY: str = ""
    ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"
    ODDS_API_REGIONS: str = "eu"
    ODDS_API_FOOTBALL_SPORTS: str = "soccer_epl,soccer_uefa_champs_league"
    ODDS_API_DOTA_SPORTS: str = ""

    SCHEDULER_FETCH_INTERVAL_MINUTES: int = 30
    SCHEDULER_SETTLE_INTERVAL_MINUTES: int = 5
    SETTLE_GRACE_MINUTES: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
