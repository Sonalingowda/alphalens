"""Environment-based application settings."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when environment configuration is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    app_name: str
    host: str
    port: int
    api_workers: int
    log_level: str
    cors_allowed_origins: tuple[str, ...]
    market_data_base_url: str
    market_data_timeout_seconds: float
    history_backfill_start: datetime
    history_backfill_max_pages: int
    database_url: str
    prediction_api_max_request_bytes: int


def load_settings() -> Settings:
    settings = Settings(
        environment=os.getenv(
            "ALPHALENS_ENVIRONMENT",
            "development",
        ).lower(),
        app_name=os.getenv("ALPHALENS_API_NAME", "AlphaLens API"),
        host=os.getenv("ALPHALENS_API_HOST", "127.0.0.1"),
        port=int(os.getenv("ALPHALENS_API_PORT", "8000")),
        api_workers=int(os.getenv("ALPHALENS_API_WORKERS", "1")),
        log_level=os.getenv("ALPHALENS_LOG_LEVEL", "INFO").upper(),
        cors_allowed_origins=_environment_origins(
            "ALPHALENS_CORS_ALLOWED_ORIGINS",
            "http://127.0.0.1:3000,http://localhost:3000",
        ),
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
        prediction_api_max_request_bytes=int(
            os.getenv(
                "ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES",
                "32768",
            )
        ),
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    if settings.environment not in {
        "development",
        "test",
        "production",
    }:
        raise ConfigurationError(
            "ALPHALENS_ENVIRONMENT must be development, test, or production."
        )
    if not settings.app_name.strip():
        raise ConfigurationError("ALPHALENS_API_NAME cannot be empty.")
    if not 1 <= settings.port <= 65_535:
        raise ConfigurationError(
            "ALPHALENS_API_PORT must be between 1 and 65535."
        )
    if not 1 <= settings.api_workers <= 16:
        raise ConfigurationError(
            "ALPHALENS_API_WORKERS must be between 1 and 16."
        )
    if settings.log_level not in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }:
        raise ConfigurationError(
            "ALPHALENS_LOG_LEVEL is not a supported logging level."
        )
    if not 0 < settings.market_data_timeout_seconds <= 120:
        raise ConfigurationError(
            "ALPHALENS_MARKET_DATA_TIMEOUT_SECONDS must be in (0, 120]."
        )
    if settings.history_backfill_max_pages <= 0:
        raise ConfigurationError(
            "ALPHALENS_HISTORY_BACKFILL_MAX_PAGES must be positive."
        )
    if not 1_024 <= settings.prediction_api_max_request_bytes <= 1_048_576:
        raise ConfigurationError(
            "ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES must be between "
            "1024 and 1048576."
        )
    database = urlsplit(settings.database_url)
    if database.scheme != "postgresql+asyncpg" or not database.hostname:
        raise ConfigurationError(
            "ALPHALENS_DATABASE_URL must be a postgresql+asyncpg URL."
        )
    for origin in settings.cors_allowed_origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigurationError(
                "Every CORS origin must be an HTTP(S) origin without a path."
            )
    if settings.environment == "production":
        if settings.host in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigurationError(
                "Production ALPHALENS_API_HOST cannot be loopback-only."
            )
        if not settings.cors_allowed_origins:
            raise ConfigurationError(
                "Production requires at least one explicit CORS origin."
            )
        if any(
            urlsplit(origin).hostname
            in {"127.0.0.1", "localhost", "::1"}
            for origin in settings.cors_allowed_origins
        ):
            raise ConfigurationError(
                "Production CORS origins cannot target localhost."
            )
        password = database.password or ""
        if (
            password in {"", "alphalens_dev", "change-me", "replace-me"}
            or password.startswith("replace-")
        ):
            raise ConfigurationError(
                "Production database credentials must use a non-placeholder "
                "password."
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


def _environment_origins(
    name: str,
    default: str,
) -> tuple[str, ...]:
    raw_value = os.getenv(name, default)
    origins = tuple(
        value.strip().rstrip("/")
        for value in raw_value.split(",")
        if value.strip()
    )
    if len(origins) != len(set(origins)):
        raise ConfigurationError(f"{name} contains duplicate origins.")
    if "*" in origins:
        raise ConfigurationError(f"{name} cannot contain a wildcard.")
    return origins
