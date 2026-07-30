"""Structured JSON logging without external logging dependencies."""

from datetime import datetime, timezone
import json
import logging
from typing import Any


class JsonLogFormatter(logging.Formatter):
    """Render one machine-readable JSON object per log event."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in (
            "request_path",
            "http_method",
            "status_code",
            "latency_microseconds",
            "error_code",
            "prediction_hash",
            "artifact_id",
        ):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )


def configure_structured_logging(level: str) -> None:
    """Configure application and Uvicorn logs with a shared JSON format."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    numeric_level = getattr(logging, level)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        current = logging.getLogger(name)
        current.handlers.clear()
        current.propagate = True
        current.setLevel(numeric_level)
