"""Production entry point for the read-only live prediction API."""

from app.api.application import create_prediction_app
from app.observability.logging import configure_structured_logging
from app.settings import load_settings


settings = load_settings()
configure_structured_logging(settings.log_level)
app = create_prediction_app(
    maximum_request_bytes=settings.prediction_api_max_request_bytes,
    cors_allowed_origins=settings.cors_allowed_origins,
)
