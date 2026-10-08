"""PostgreSQL transaction-boundary tests for the research-cycle orchestrator."""

from datetime import datetime, timezone
import os
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, skipUnless
from uuid import uuid4

from sqlalchemy import text

from app.persistence import research_cycle
from app.persistence.database import engine, session_factory
from app.validation.splits import WalkForwardConfig


@skipUnless(
    os.getenv("ALPHALENS_RUN_POSTGRES_TESTS") == "1",
    "PostgreSQL integration environment is not enabled.",
)
class ResearchCycleTransactionIntegrationTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await engine.dispose()

    async def asyncTearDown(self) -> None:
        await engine.dispose()

    async def test_initial_read_is_closed_before_first_persistence_transaction(self) -> None:
        batch = SimpleNamespace(id=uuid4(), source_data_hash="transaction-test")
        candles = SimpleNamespace(
            row_count=0,
            date_range_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_range_end=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        events: list[str] = []

        async with session_factory() as session:
            async def verify(db_session):
                await db_session.execute(text("SELECT 1"))
                return batch, candles

            async def first_persistence_stage(db_session, _batch):
                async with db_session.begin():
                    await db_session.execute(text("SELECT 1"))
                events.append("feature")
                return SimpleNamespace(id=uuid4())

            async def controlled_failure(*_args):
                raise RuntimeError("controlled downstream failure")

            with (
                self._patch(research_cycle, "_verify_market_candle_input", verify),
                self._patch(research_cycle, "_ensure_feature_run", first_persistence_stage),
                self._patch(
                    research_cycle,
                    "_ensure_target_run",
                    controlled_failure,
                ),
            ):
                summary = await research_cycle.run_research_cycle(
                    session,
                    validation_config=WalkForwardConfig(),
                    test_evidence=object(),
                )

            self.assertEqual(summary.failure_stage, "target_persistence")
            self.assertEqual(summary.failure_reason, "RuntimeError: controlled downstream failure")
            self.assertEqual(events, ["feature"])
            self.assertFalse(session.in_transaction())

    async def test_failing_persistence_transaction_rolls_back_its_records(self) -> None:
        batch = SimpleNamespace(id=uuid4(), source_data_hash="rollback-test")
        candles = SimpleNamespace(
            row_count=0,
            date_range_start=None,
            date_range_end=None,
        )

        async with session_factory() as session:
            await session.execute(
                text("CREATE TEMP TABLE research_cycle_transaction_marker (value integer)")
            )
            await session.commit()

            async def verify(db_session):
                await db_session.execute(text("SELECT 1"))
                return batch, candles

            async def failing_persistence_stage(db_session, _batch):
                async with db_session.begin():
                    await db_session.execute(
                        text(
                            "INSERT INTO research_cycle_transaction_marker(value) "
                            "VALUES (1)"
                        )
                    )
                    raise RuntimeError("controlled persistence failure")

            with (
                self._patch(research_cycle, "_verify_market_candle_input", verify),
                self._patch(research_cycle, "_ensure_feature_run", failing_persistence_stage),
            ):
                summary = await research_cycle.run_research_cycle(
                    session,
                    validation_config=WalkForwardConfig(),
                    test_evidence=object(),
                )

            self.assertFalse(session.in_transaction())
            marker_count = await session.scalar(
                text("SELECT count(*) FROM research_cycle_transaction_marker")
            )
            await session.rollback()
            self.assertEqual(summary.failure_stage, "feature_persistence")
            self.assertEqual(summary.failure_reason, "RuntimeError: controlled persistence failure")
            self.assertEqual(marker_count, 0)
            self.assertFalse(session.in_transaction())

    @staticmethod
    def _patch(module, name: str, function):
        from unittest.mock import AsyncMock, patch

        return patch.object(module, name, AsyncMock(side_effect=function))
