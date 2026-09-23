"""Regression coverage for live snapshot outcome-candle selection."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.repositories import RepositoryPage, ScopedRepositoryQuery
from app.prediction_api import _LiveCandleQueryAdapter


UTC = timezone.utc


def _snapshot(timestamp: datetime, available_at: datetime) -> SimpleNamespace:
    candle = SimpleNamespace(
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("10"),
    )
    return SimpleNamespace(
        scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
        candles=(candle,),
        audit=SimpleNamespace(available_at=available_at),
    )


class _SnapshotRepository:
    def __init__(self, snapshots: tuple[SimpleNamespace, ...]) -> None:
        self.snapshots = snapshots
        self.queries: list[ScopedRepositoryQuery] = []

    async def get_by_scope(self, query: ScopedRepositoryQuery) -> RepositoryPage:
        self.queries.append(query)
        return RepositoryPage(items=self.snapshots, as_of=query.as_of)


class LiveSnapshotCandleQueryTests(IsolatedAsyncioTestCase):
    async def test_live_snapshot_at_boundary_is_selected(self) -> None:
        signal = datetime(2026, 9, 23, 15, 45, 0, 18000, tzinfo=UTC)
        valid_until = datetime(2026, 9, 23, 15, 55, 0, 18000, tzinfo=UTC)
        repository = _SnapshotRepository(
            (
                _snapshot(
                    datetime(2026, 9, 23, 15, 45, tzinfo=UTC),
                    datetime(2026, 9, 23, 15, 50, 0, 999000, tzinfo=UTC),
                ),
                _snapshot(
                    datetime(2026, 9, 23, 15, 50, tzinfo=UTC),
                    datetime(2026, 9, 23, 15, 55, 0, 999000, tzinfo=UTC),
                ),
            )
        )

        candles = await _LiveCandleQueryAdapter(repository).query(
            instrument="BTCUSDT",
            timeframe="5m",
            after=signal,
            up_to_and_including=valid_until,
        )

        self.assertEqual(
            [candle["timestamp"] for candle in candles],
            [datetime(2026, 9, 23, 15, 50, tzinfo=UTC)],
        )
        self.assertEqual(
            repository.queries[0].scope,
            MarketScope(instrument="BTCUSDT", timeframe="5m"),
        )
        self.assertGreater(repository.queries[0].as_of, valid_until)
