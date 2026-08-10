"""PostgreSQL repository parity tests enabled by integration environments."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from unittest import IsolatedAsyncioTestCase, skipUnless

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import (
    MarketSnapshotPostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import EntityId
from app.persistence.database import engine, session_factory
from tests.test_opportunity_domain_models import _market_snapshot


@skipUnless(
    os.getenv("ALPHALENS_RUN_POSTGRES_TESTS") == "1",
    "PostgreSQL integration environment is not enabled.",
)
class PostgreSQLRepositoryIntegrationTests(IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        await engine.dispose()

    async def test_save_replay_read_and_database_immutability(self) -> None:
        repository = MarketSnapshotPostgreSQLRepository(session_factory)
        snapshot = _market_snapshot()

        self.assertEqual(await repository.save(snapshot), snapshot)
        self.assertEqual(await repository.save(snapshot), snapshot)
        restored = await repository.get_by_id(EntityId(snapshot.snapshot_id))

        self.assertEqual(restored, snapshot)
        self.assertEqual(restored.canonical_sha256(), snapshot.canonical_sha256())
        with self.assertRaises(SQLAlchemyError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE immutable_runtime_aggregates "
                        "SET revision = 2 WHERE entity_id = :entity_id"
                    ),
                    {"entity_id": snapshot.snapshot_id},
                )

    async def test_market_snapshot_scope_is_chronological_and_latest_is_newest(self) -> None:
        repository = MarketSnapshotPostgreSQLRepository(session_factory)
        first = _market_snapshot_at(
            datetime(2026, 8, 4, 13, 40, tzinfo=timezone.utc),
            "market.snapshot.early",
            "market.candle.early",
        )
        second = _market_snapshot_at(
            datetime(2026, 8, 4, 13, 45, tzinfo=timezone.utc),
            "market.snapshot.middle",
            "market.candle.middle",
        )
        third = _market_snapshot_at(
            datetime(2026, 8, 4, 13, 50, tzinfo=timezone.utc),
            "market.snapshot.late",
            "market.candle.late",
        )

        await repository.save_batch((third, first, second))
        from app.opportunity_intelligence.repositories import ScopedRepositoryQuery

        query = ScopedRepositoryQuery(
            scope=MarketScope(instrument="TESTBTC", timeframe=CandleTimeframe.MINUTE_5.value),
            as_of=datetime(2026, 8, 4, 13, 55, tzinfo=timezone.utc),
            limit=10,
        )
        page = await repository.get_by_scope(query)
        latest = await repository.get_latest(
            replace(query, limit=1)
        )

        self.assertEqual(
            tuple(item.candles[0].timestamp for item in page.items),
            (
                datetime(2026, 8, 4, 13, 40, tzinfo=timezone.utc),
                datetime(2026, 8, 4, 13, 45, tzinfo=timezone.utc),
                datetime(2026, 8, 4, 13, 50, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            latest.candles[0].timestamp,
            datetime(2026, 8, 4, 13, 50, tzinfo=timezone.utc),
        )

    async def test_market_snapshot_scope_keeps_prefix_before_trailing_gap(self) -> None:
        repository = MarketSnapshotPostgreSQLRepository(session_factory)
        scope = MarketScope(
            instrument="TESTBTC_GAP",
            timeframe=CandleTimeframe.MINUTE_5.value,
        )
        first = _market_snapshot_at(
            datetime(2026, 8, 10, 17, 10, tzinfo=timezone.utc),
            "market.snapshot.gap.one.20260810",
            "market.candle.gap.one.20260810",
            scope,
        )
        second = _market_snapshot_at(
            datetime(2026, 8, 10, 17, 15, tzinfo=timezone.utc),
            "market.snapshot.gap.two.20260810",
            "market.candle.gap.two.20260810",
            scope,
        )
        third = _market_snapshot_at(
            datetime(2026, 8, 10, 17, 20, tzinfo=timezone.utc),
            "market.snapshot.gap.three.20260810",
            "market.candle.gap.three.20260810",
            scope,
        )
        fourth = _market_snapshot_at(
            datetime(2026, 8, 10, 17, 25, tzinfo=timezone.utc),
            "market.snapshot.gap.four.20260810",
            "market.candle.gap.four.20260810",
            scope,
        )
        trailing = _market_snapshot_at(
            datetime(2026, 8, 10, 17, 35, tzinfo=timezone.utc),
            "market.snapshot.gap.trailing.20260810",
            "market.candle.gap.trailing.20260810",
            scope,
        )

        await repository.save_batch((trailing, first, second, third, fourth))
        from app.opportunity_intelligence.repositories import ScopedRepositoryQuery

        query = ScopedRepositoryQuery(
            scope=scope,
            as_of=datetime(2026, 8, 10, 17, 40, tzinfo=timezone.utc),
            limit=10,
        )
        page = await repository.get_by_scope(query)
        latest = await repository.get_latest(replace(query, limit=1))

        self.assertEqual(
            tuple(item.candles[0].timestamp for item in page.items),
            (
                datetime(2026, 8, 10, 17, 10, tzinfo=timezone.utc),
                datetime(2026, 8, 10, 17, 15, tzinfo=timezone.utc),
                datetime(2026, 8, 10, 17, 20, tzinfo=timezone.utc),
                datetime(2026, 8, 10, 17, 25, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            tuple(item.snapshot_id for item in page.items),
            (
                "market.snapshot.gap.one.20260810",
                "market.snapshot.gap.two.20260810",
                "market.snapshot.gap.three.20260810",
                "market.snapshot.gap.four.20260810",
            ),
        )
        self.assertIsNone(page.next_cursor)
        self.assertEqual(
            latest.candles[0].timestamp,
            datetime(2026, 8, 10, 17, 35, tzinfo=timezone.utc),
        )


def _market_snapshot_at(
    timestamp: datetime,
    snapshot_id: str,
    candle_id: str,
    scope: MarketScope | None = None,
):
    scope = scope or MarketScope(
        instrument="TESTBTC",
        timeframe=CandleTimeframe.MINUTE_5.value,
    )
    base = _market_snapshot()
    candle = replace(
        base.candles[0],
        candle_id=candle_id,
        timestamp=timestamp,
        available_at=timestamp,
    )
    audit = replace(
        base.audit,
        created_at=timestamp,
        evidence_cutoff=timestamp,
        available_at=timestamp,
    )
    return replace(
        base,
        snapshot_id=snapshot_id,
        scope=scope,
        candles=(candle,),
        audit=audit,
    )
