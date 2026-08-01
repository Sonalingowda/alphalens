"""Transactional intraday feature persistence tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import UUID

from app.features.contracts import FeatureComputationError
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import (
    _feature_value_row,
    _persist_source_memberships,
    _promote_active_run,
    _verify_stored_values,
    persist_intraday_feature_result,
)
from app.persistence.models import (
    EngineeredFeatureRecord,
    FeaturePipelineRunRecord,
    FeaturePipelineRunSourceRecord,
)


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000001")


class IntradayFeaturePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_transaction_persists_and_promotes_in_final_step(
        self,
    ) -> None:
        snapshot, result = _pipeline_evidence()
        session = _FakeSession()
        stored_values = tuple(
            SimpleNamespace(id=index + 1) for index in range(len(result.values))
        )
        events = session.events

        async def record(name, return_value=None):
            events.append(name)
            return return_value

        async def verify_source(*_args):
            return await record("verify_source")

        async def persist_sources(*_args):
            return await record("persist_sources")

        async def reconcile_values(*_args):
            return await record(
                "reconcile_values",
                (stored_values, len(stored_values)),
            )

        async def persist_memberships(*_args):
            return await record("persist_memberships")

        async def persist_dependencies(*_args):
            return await record("persist_dependencies")

        async def verify_memberships(*_args, **_kwargs):
            return await record(
                "verify_memberships",
                (len(stored_values), len(result.dependency_memberships)),
            )

        async def promote(*_args):
            return await record("promote")

        with (
            patch(
                "app.persistence.intraday_features."
                "_verify_source_snapshot_against_database",
                new=AsyncMock(side_effect=verify_source),
            ),
            patch(
                "app.persistence.intraday_features._persist_source_memberships",
                new=AsyncMock(side_effect=persist_sources),
            ),
            patch(
                "app.persistence.intraday_features._reconcile_feature_values",
                new=AsyncMock(side_effect=reconcile_values),
            ),
            patch(
                "app.persistence.intraday_features._persist_value_memberships",
                new=AsyncMock(side_effect=persist_memberships),
            ),
            patch(
                "app.persistence.intraday_features._persist_dependency_memberships",
                new=AsyncMock(side_effect=persist_dependencies),
            ),
            patch(
                "app.persistence.intraday_features._verify_run_memberships",
                new=AsyncMock(side_effect=verify_memberships),
            ),
            patch(
                "app.persistence.intraday_features._promote_active_run",
                new=AsyncMock(side_effect=promote),
            ),
        ):
            persisted = await persist_intraday_feature_result(
                session,
                snapshot,
                result,
            )

        self.assertEqual(persisted.pipeline_version, "2.7.0")
        self.assertEqual(
            persisted.inserted_value_count,
            len(result.values),
        )
        self.assertEqual(persisted.reused_value_count, 0)
        self.assertEqual(
            persisted.membership_count,
            len(result.values),
        )
        self.assertEqual(
            persisted.dependency_membership_count,
            len(result.dependency_memberships),
        )
        self.assertTrue(persisted.is_active)
        self.assertEqual(events[-2:], ["promote", "transaction_commit"])
        run_record = session.added[0]
        self.assertEqual(
            run_record.pipeline_version,
            INTRADAY_PIPELINE_VERSION,
        )
        self.assertEqual(run_record.source_data_hash, result.source_data_hash)
        self.assertEqual(
            run_record.source_provenance_hash,
            result.source_provenance_hash,
        )
        self.assertEqual(run_record.registry_hash, result.registry_hash)
        self.assertEqual(run_record.result_hash, result.result_hash)
        self.assertEqual(
            run_record.persisted_value_count,
            len(result.values),
        )

    async def test_failure_rolls_back_and_never_promotes(self) -> None:
        snapshot, result = _pipeline_evidence()
        session = _FakeSession()
        promotion = AsyncMock()

        with (
            patch(
                "app.persistence.intraday_features."
                "_verify_source_snapshot_against_database",
                new=AsyncMock(),
            ),
            patch(
                "app.persistence.intraday_features._persist_source_memberships",
                new=AsyncMock(side_effect=RuntimeError("injected failure")),
            ),
            patch(
                "app.persistence.intraday_features._promote_active_run",
                new=promotion,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "injected failure",
            ):
                await persist_intraday_feature_result(
                    session,
                    snapshot,
                    result,
                )

        promotion.assert_not_awaited()
        self.assertEqual(
            session.events[-1],
            "transaction_rollback:RuntimeError",
        )

    async def test_tampered_result_is_rejected_before_transaction(
        self,
    ) -> None:
        snapshot, result = _pipeline_evidence()
        session = _FakeSession()

        with self.assertRaisesRegex(
            FeatureComputationError,
            "integrity verification",
        ):
            await persist_intraday_feature_result(
                session,
                snapshot,
                replace(result, result_hash="0" * 64),
            )

        self.assertEqual(session.events, [])

    async def test_source_memberships_retain_each_batch_hash(self) -> None:
        snapshot, _result = _pipeline_evidence(multiple_batches=True)
        session = _FakeSession()
        run_id = UUID("00000000-0000-0000-0000-000000000020")

        await _persist_source_memberships(
            session,
            run_id,
            snapshot,
            datetime.now(timezone.utc),
        )

        memberships = tuple(
            value
            for value in session.added
            if isinstance(value, FeaturePipelineRunSourceRecord)
        )
        self.assertEqual(len(memberships), 2)
        self.assertEqual(
            sum(value.source_candle_count for value in memberships),
            len(snapshot.observations),
        )
        self.assertTrue(
            all(len(value.source_subset_hash) == 64 for value in memberships)
        )

    def test_feature_value_row_retains_candle_batch_provenance(
        self,
    ) -> None:
        snapshot, result = _pipeline_evidence(multiple_batches=True)
        value = result.values[-1]
        source_batch_by_timestamp = {
            observation.candle.timestamp: observation.ingestion_batch_id
            for observation in snapshot.observations
        }
        row = _feature_value_row(
            value,
            UUID("00000000-0000-0000-0000-000000000020"),
            result,
            source_batch_by_timestamp,
            datetime.now(timezone.utc),
        )

        self.assertEqual(row["pipeline_version"], "2.7.0")
        self.assertEqual(
            row["source_ingestion_batch_id"],
            source_batch_by_timestamp[value.candle_timestamp],
        )
        self.assertEqual(row["available_at"], value.available_at)
        self.assertEqual(row["feature_value"], value.value)

    def test_immutable_stored_value_mismatch_is_rejected(self) -> None:
        snapshot, result = _pipeline_evidence()
        expected = result.values[0]
        source_batch_by_timestamp = {
            observation.candle.timestamp: observation.ingestion_batch_id
            for observation in snapshot.observations
        }
        stored = EngineeredFeatureRecord(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe="5m",
            candle_timestamp=expected.candle_timestamp,
            available_at=expected.available_at,
            feature_name=expected.output_name,
            feature_value=expected.value + Decimal("0.000000000000000001"),
            pipeline_version="2.0.0",
            source_ingestion_batch_id=_BATCH_ID,
            computation_run_id=UUID("00000000-0000-0000-0000-000000000020"),
            computed_at=datetime.now(timezone.utc),
        )

        with self.assertRaisesRegex(
            FeatureComputationError,
            "differs from the result",
        ):
            _verify_stored_values(
                (stored,),
                result.values,
                source_batch_by_timestamp,
            )

    async def test_incomplete_run_cannot_be_promoted(self) -> None:
        run = _run_record()
        run.persisted_value_count = 4
        session = _FakeSession()

        with self.assertRaisesRegex(
            FeatureComputationError,
            "Incomplete feature run",
        ):
            await _promote_active_run(
                session,
                run,
                datetime.now(timezone.utc),
            )

        self.assertFalse(run.is_active)

    async def test_complete_run_promotion_deactivates_prior_run(self) -> None:
        run = _run_record()
        session = _FakeSession()

        await _promote_active_run(
            session,
            run,
            datetime.now(timezone.utc),
        )

        self.assertTrue(run.is_active)
        self.assertIn("execute", session.events)
        self.assertEqual(session.events[-1], "flush")


class IntradayFeaturePersistenceSchemaTests(unittest.TestCase):
    def test_run_schema_contains_complete_hash_provenance(self) -> None:
        columns = FeaturePipelineRunRecord.__table__.columns
        self.assertIn("source_data_hash", columns)
        self.assertIn("source_provenance_hash", columns)
        self.assertIn("registry_hash", columns)
        self.assertIn("result_hash", columns)

        constraints = {
            constraint.name
            for constraint in FeaturePipelineRunRecord.__table__.constraints
        }
        self.assertIn(
            "ck_feature_pipeline_runs_result_hashes",
            constraints,
        )


class _FakeTransaction:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def __aenter__(self):
        self.events.append("transaction_enter")
        return self

    async def __aexit__(self, exc_type, _exc, _traceback):
        if exc_type is None:
            self.events.append("transaction_commit")
        else:
            self.events.append(f"transaction_rollback:{exc_type.__name__}")
        return False


class _FakeSession:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.added: list[object] = []

    def begin(self) -> _FakeTransaction:
        self.events.append("transaction_begin")
        return _FakeTransaction(self.events)

    def add(self, value: object) -> None:
        self.events.append("add")
        self.added.append(value)

    async def flush(self) -> None:
        self.events.append("flush")

    async def execute(self, _statement):
        self.events.append("execute")
        return None


def _pipeline_evidence(*, multiple_batches: bool = False):
    start = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
    second_batch_id = UUID("00000000-0000-0000-0000-000000000002")
    observations = tuple(
        SourceCandleObservation(
            candle=Candle(
                timestamp=start + timedelta(minutes=5 * index),
                open=Decimal(100 + index),
                high=Decimal(102 + index),
                low=Decimal(99 + index),
                close=Decimal("101.5") + Decimal(index),
                volume=Decimal(10 + index),
            ),
            ingestion_batch_id=(
                second_batch_id if multiple_batches and index == 2 else _BATCH_ID
            ),
            is_complete=True,
        )
        for index in range(3)
    )
    snapshot = build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=CandleTimeframe.MINUTE_5,
        observations=observations,
    )
    return snapshot, run_intraday_feature_pipeline(snapshot)


def _run_record() -> FeaturePipelineRunRecord:
    now = datetime.now(timezone.utc)
    return FeaturePipelineRunRecord(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        pipeline_version="2.0.0",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="5m",
        source_ingestion_batch_id=_BATCH_ID,
        source_candle_count=3,
        source_range_start=now,
        source_range_end=now,
        source_data_hash="1" * 64,
        source_provenance_hash="2" * 64,
        result_hash="3" * 64,
        registry_hash="4" * 64,
        registry_schema_version="1.0.0",
        availability_contract_version="1.0.0",
        registry_snapshot={},
        point_in_time_validated=True,
        feature_value_count=5,
        persisted_value_count=5,
        is_active=False,
        computed_at=now,
    )


if __name__ == "__main__":
    unittest.main()
