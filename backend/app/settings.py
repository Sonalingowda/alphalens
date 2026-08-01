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
    database_pool_size: int
    database_max_overflow: int
    database_pool_timeout_seconds: float
    redis_url: str
    prediction_api_max_request_bytes: int
    metrics_enabled: bool
    worker_concurrency: int
    worker_poll_seconds: float
    worker_max_retries: int


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
        database_url=_secret_environment(
            "ALPHALENS_DATABASE_URL",
            "postgresql+asyncpg://alphalens:alphalens_dev@127.0.0.1:5432/alphalens",
        ),
        database_pool_size=int(os.getenv("ALPHALENS_DATABASE_POOL_SIZE", "5")),
        database_max_overflow=int(
            os.getenv("ALPHALENS_DATABASE_MAX_OVERFLOW", "10")
        ),
        database_pool_timeout_seconds=float(
            os.getenv("ALPHALENS_DATABASE_POOL_TIMEOUT_SECONDS", "30")
        ),
        redis_url=_secret_environment(
            "ALPHALENS_REDIS_URL",
            "redis://127.0.0.1:6379/0",
        ),
        prediction_api_max_request_bytes=int(
            os.getenv(
                "ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES",
                "32768",
            )
        ),
        metrics_enabled=_environment_bool("ALPHALENS_METRICS_ENABLED", True),
        worker_concurrency=int(os.getenv("ALPHALENS_WORKER_CONCURRENCY", "2")),
        worker_poll_seconds=float(os.getenv("ALPHALENS_WORKER_POLL_SECONDS", "1")),
        worker_max_retries=int(os.getenv("ALPHALENS_WORKER_MAX_RETRIES", "3")),
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    if settings.environment not in {
        "development",
        "staging",
        "test",
        "production",
    }:
        raise ConfigurationError(
            "ALPHALENS_ENVIRONMENT must be development, test, staging, or production."
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
    if not 1 <= settings.database_pool_size <= 100:
        raise ConfigurationError("ALPHALENS_DATABASE_POOL_SIZE must be in [1, 100].")
    if not 0 <= settings.database_max_overflow <= 200:
        raise ConfigurationError(
            "ALPHALENS_DATABASE_MAX_OVERFLOW must be in [0, 200]."
        )
    if not 1 <= settings.database_pool_timeout_seconds <= 300:
        raise ConfigurationError(
            "ALPHALENS_DATABASE_POOL_TIMEOUT_SECONDS must be in [1, 300]."
        )
    redis = urlsplit(settings.redis_url)
    if redis.scheme not in {"redis", "rediss"} or not redis.hostname:
        raise ConfigurationError(
            "ALPHALENS_REDIS_URL must be a redis:// or rediss:// URL."
        )
    if not 1 <= settings.worker_concurrency <= 64:
        raise ConfigurationError("ALPHALENS_WORKER_CONCURRENCY must be in [1, 64].")
    if not 0.05 <= settings.worker_poll_seconds <= 60:
        raise ConfigurationError(
            "ALPHALENS_WORKER_POLL_SECONDS must be in [0.05, 60]."
        )
    if not 0 <= settings.worker_max_retries <= 20:
        raise ConfigurationError("ALPHALENS_WORKER_MAX_RETRIES must be in [0, 20].")
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
        if not redis.password or redis.password in {
            "change-me",
            "replace-me",
            "alphalens_dev",
        }:
            raise ConfigurationError(
                "Production Redis credentials must use a non-placeholder password."
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


def _environment_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean value.")


def _secret_environment(name: str, default: str) -> str:
    direct = os.getenv(name)
    file_path = os.getenv(f"{name}_FILE")
    if direct is not None and file_path is not None:
        raise ConfigurationError(f"Set only one of {name} and {name}_FILE.")
    if file_path is None:
        return direct if direct is not None else default
    try:
        with open(file_path, encoding="utf-8") as secret_file:
            value = secret_file.read().strip()
    except OSError as error:
        raise ConfigurationError(f"Cannot read secret file for {name}.") from error
    if not value:
        raise ConfigurationError(f"Secret file for {name} is empty.")
    return value
