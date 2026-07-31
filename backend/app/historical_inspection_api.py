"""Entry point for the read-only historical operational inspection API."""

from app.api.historical_inspection import create_historical_inspection_app
from app.observability.logging import configure_structured_logging
from app.settings import load_settings


settings = load_settings()
configure_structured_logging(settings.log_level)
app = create_historical_inspection_app(
    maximum_request_bytes=settings.prediction_api_max_request_bytes,
)
