"""Service ports for resolving immutable market and feature snapshots."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import FeatureSnapshot, MarketSnapshot
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery


@runtime_checkable
class MarketScannerService(Protocol):
    """Resolve fresh canonical market state without producing a signal."""

    async def scan(self, query: ScopedRepositoryQuery) -> MarketSnapshot:
        """Return a validated snapshot or fail closed without a market result."""
        ...


@runtime_checkable
class FeatureSnapshotService(Protocol):
    """Resolve the feature snapshot compatible with one market snapshot."""

    async def resolve(self, market_snapshot: MarketSnapshot) -> FeatureSnapshot:
        """Return compatible registered features or fail closed."""
        ...

