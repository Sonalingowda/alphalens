"""Concrete, fail-closed runtime market-context generation."""

from app.runtime_context.service import (
    RUNTIME_CONTEXT_SERVICE_VERSION,
    RuntimeMarketContextService,
)


__all__ = (
    "RUNTIME_CONTEXT_SERVICE_VERSION",
    "RuntimeMarketContextService",
)
