"""Environment-based application settings."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    host: str
    port: int
    market_data_base_url: str
    market_data_timeout_seconds: float
    history_backfill_start: datetime
    history_backfill_max_pages: int
    database_url: str


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("ALPHALENS_API_NAME", "AlphaLens API"),
        host=os.getenv("ALPHALENS_API_HOST", "127.0.0.1"),
        port=int(os.getenv("ALPHALENS_API_PORT", "8000")),
        market_data_base_url=os.getenv(
            "ALPHALENS_MARKET_DATA_BASE_URL",
            "https://api.kraken.com",
        ),
        market_data_timeout_seconds=float(
            os.getenv("ALPHALENS_MARKET_DATA_TIMEOUT_SECONDS", "10")
        ),
        history_backfill_start=_environment_datetime(
            "ALPHALENS_HISTORY_BACKFILL_START",
            "2010-01-01T00:00:00+00:00",
        ),
        history_backfill_max_pages=int(
            os.getenv("ALPHALENS_HISTORY_BACKFILL_MAX_PAGES", "100")
        ),
        database_url=os.getenv(
            "ALPHALENS_DATABASE_URL",
            "postgresql+asyncpg://alphalens:alphalens_dev@127.0.0.1:5432/alphalens",
        ),
    )


def _environment_datetime(name: str, default: str) -> datetime:
    raw_value = os.getenv(name, default)
    try:
        value = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 datetime.") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a UTC offset.")
    return value.astimezone(timezone.utc)
