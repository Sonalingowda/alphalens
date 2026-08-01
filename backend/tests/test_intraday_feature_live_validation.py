"""Integration tests for live intraday feature validation orchestration."""

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, patch
from uuid import UUID

from app.features.contracts import FeatureComputationError
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    IntradaySourceSnapshot,
    SourceCandleObservation,
    build_intraday_source_snapshot,
)
from app.features.live_validation import (
    _verify_ingestion_item,
    validate_live_intraday_feature_pipeline,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.history import HistoricalSample
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import timeframe_duration, validate_candles
from app.persistence.candles import CandlePersistenceResult
from app.persistence.intraday import (
    IntradayIngestionItem,
    IntradayIngestionResult,
)
from app.persistence.intraday_features import (
    IntradayFeaturePersistenceResult,
    StoredIntradayFeatureRunEvidence,
)


_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


class LiveIntradayFeatureValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_live_flow_verifies_all_timeframes(self) -> None:
        ingestion, snapshots = _ingestion_and_snapshots()
        persistence_calls: dict[CandleTimeframe, int] = {
            timeframe: 0 for timeframe in _TIMEFRAMES
        }
        run_evidence: dict[UUID, StoredIntradayFeatureRunEvidence] = {}

        async def load_snapshot(_session, timeframe):
            return snapshots[timeframe]

        async def count_values(_session, _timeframe):
            return 0

        async def persist(_session, snapshot, result):
            timeframe = snapshot.timeframe
            persistence_calls[timeframe] += 1
            sequence = persistence_calls[timeframe]
            run_id = UUID(
                f"00000000-0000-0000-0000-{_minutes(timeframe):04d}{sequence:08d}"
            )
            inserted = len(result.values) if sequence == 1 else 0
            evidence = _stored_evidence(
                run_id,
                result,
                is_active=sequence == 2,
            )
            run_evidence[run_id] = evidence
            if sequence == 2:
                first_id = UUID(
                    f"00000000-0000-0000-0000-{_minutes(timeframe):04d}00000001"
                )
                run_evidence[first_id] = _stored_evidence(
                    first_id,
                    result,
                    is_active=False,
                )
            return IntradayFeaturePersistenceResult(
                feature_run_id=run_id,
                pipeline_version=INTRADAY_PIPELINE_VERSION,
                timeframe=timeframe.value,
                source_data_hash=result.source_data_hash,
                source_provenance_hash=result.source_provenance_hash,
                registry_hash=result.registry_hash,
                result_hash=result.result_hash,
                source_candle_count=len(snapshot.observations),
                source_batch_count=1,
                computed_value_count=len(result.values),
                inserted_value_count=inserted,
                reused_value_count=len(result.values) - inserted,
                membership_count=len(result.values),
                dependency_membership_count=len(result.dependency_memberships),
                is_active=True,
            )

        async def get_evidence(_session, run_id):
            return run_evidence[run_id]

        with (
            patch(
                "app.features.live_validation.ingest_btc_usd_intraday",
                new=AsyncMock(return_value=ingestion),
            ),
            patch(
                "app.features.live_validation.load_intraday_source_snapshot",
                new=AsyncMock(side_effect=load_snapshot),
            ),
            patch(
                "app.features.live_validation.count_intraday_feature_values",
                new=AsyncMock(side_effect=count_values),
            ),
            patch(
                "app.features.live_validation.persist_intraday_feature_result",
                new=AsyncMock(side_effect=persist),
            ),
            patch(
                "app.features.live_validation.get_stored_intraday_feature_run_evidence",
                new=AsyncMock(side_effect=get_evidence),
            ),
            patch(
                "app.features.live_validation.count_active_intraday_feature_runs",
                new=AsyncMock(return_value=1),
            ),
        ):
            report = await validate_live_intraday_feature_pipeline(
                object(),
                _FakeSessionMaker(),
            )

        self.assertEqual(report.pipeline_version, "2.6.0")
        self.assertEqual(
            report.registry_hash,
            INTRADAY_FEATURE_REGISTRY.configuration_hash,
        )
        self.assertEqual(
            tuple(item.timeframe for item in report.validations),
            _TIMEFRAMES,
        )
        for item in report.validations:
            self.assertGreater(item.first_inserted_value_count, 0)
            self.assertEqual(item.second_inserted_value_count, 0)
            self.assertEqual(
                item.second_reused_value_count,
                item.feature_value_count,
            )
            self.assertEqual(
                item.canonical_value_count,
                item.feature_value_count,
            )
            self.assertEqual(item.incomplete_candles_processed, 0)
            self.assertTrue(item.deterministic)
            self.assertTrue(item.active_run_verified)

    async def test_repeated_run_insertion_fails_closed(self) -> None:
        ingestion, snapshots = _ingestion_and_snapshots(
            timeframes=(CandleTimeframe.MINUTE_5,)
        )
        ingestion = IntradayIngestionResult(
            items=(
                ingestion.items[0],
                _ingestion_item(CandleTimeframe.MINUTE_10),
                _ingestion_item(CandleTimeframe.MINUTE_15),
            )
        )
        snapshots.update(
            {
                timeframe: _snapshot(timeframe)
                for timeframe in (
                    CandleTimeframe.MINUTE_10,
                    CandleTimeframe.MINUTE_15,
                )
            }
        )
        call_count = 0

        async def persist(_session, snapshot, result):
            nonlocal call_count
            call_count += 1
            return _persistence_result(
                snapshot.timeframe,
                result,
                sequence=call_count,
                inserted=(len(result.values) if call_count == 1 else 1),
            )

        with (
            patch(
                "app.features.live_validation.ingest_btc_usd_intraday",
                new=AsyncMock(return_value=ingestion),
            ),
            patch(
                "app.features.live_validation.load_intraday_source_snapshot",
                new=AsyncMock(
                    side_effect=lambda _session, timeframe: snapshots[timeframe]
                ),
            ),
            patch(
                "app.features.live_validation.count_intraday_feature_values",
                new=AsyncMock(return_value=0),
            ),
            patch(
                "app.features.live_validation.persist_intraday_feature_result",
                new=AsyncMock(side_effect=persist),
            ),
        ):
            with self.assertRaisesRegex(
                FeatureComputationError,
                "repeated persistence is not idempotent",
            ):
                await validate_live_intraday_feature_pipeline(
                    object(),
                    _FakeSessionMaker(),
                )

    def test_incomplete_ingestion_item_is_rejected(self) -> None:
        item = _ingestion_item(CandleTimeframe.MINUTE_5)
        incomplete = Candle(
            timestamp=item.sample.requested_end_exclusive,
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("10"),
        )
        invalid_sample = HistoricalSample(
            provider=item.sample.provider,
            asset_identifier=item.sample.asset_identifier,
            quote_currency=item.sample.quote_currency,
            timeframe=item.sample.timeframe,
            requested_start=item.sample.requested_start,
            requested_end_exclusive=item.sample.requested_end_exclusive,
            retrieved_at=item.sample.retrieved_at,
            candles=item.sample.candles + (incomplete,),
            validation_report=item.sample.validation_report,
        )

        with self.assertRaisesRegex(
            FeatureComputationError,
            "retained an incomplete candle",
        ):
            _verify_ingestion_item(
                IntradayIngestionItem(
                    sample=invalid_sample,
                    persistence=item.persistence,
                )
            )


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


class _FakeSessionMaker:
    def __call__(self):
        return _FakeSessionContext()


def _ingestion_and_snapshots(
    *,
    timeframes: tuple[CandleTimeframe, ...] = _TIMEFRAMES,
) -> tuple[
    IntradayIngestionResult,
    dict[CandleTimeframe, IntradaySourceSnapshot],
]:
    return (
        IntradayIngestionResult(
            items=tuple(_ingestion_item(timeframe) for timeframe in timeframes)
        ),
        {timeframe: _snapshot(timeframe) for timeframe in timeframes},
    )


def _ingestion_item(
    timeframe: CandleTimeframe,
) -> IntradayIngestionItem:
    snapshot = _snapshot(timeframe)
    candles = snapshot.candles
    duration = timeframe_duration(timeframe)
    requested_end = candles[-1].timestamp + duration
    report = validate_candles(
        candles=candles,
        timeframe=timeframe,
        expected_start=candles[0].timestamp,
        expected_end=requested_end,
    )
    sample = HistoricalSample(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=candles[0].timestamp,
        requested_end_exclusive=requested_end,
        retrieved_at=requested_end,
        candles=candles,
        validation_report=report,
        excluded_incomplete_candle_count=1,
    )
    return IntradayIngestionItem(
        sample=sample,
        persistence=CandlePersistenceResult(
            ingestion_batch_id=snapshot.source_ingestion_batch_ids[0],
            validation_passed=True,
            fetched_candle_count=len(candles),
            persisted_candle_count=len(candles),
            stored_candle_count=len(candles),
            ingestion_batch_count=1,
        ),
    )


def _snapshot(timeframe: CandleTimeframe) -> IntradaySourceSnapshot:
    start = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
    duration = timeframe_duration(timeframe)
    batch_id = UUID(f"00000000-0000-0000-0000-{_minutes(timeframe):012d}")
    observations = tuple(
        SourceCandleObservation(
            candle=Candle(
                timestamp=start + duration * index,
                open=Decimal(100 + index),
                high=Decimal(102 + index),
                low=Decimal(99 + index),
                close=Decimal("101.5") + index,
                volume=Decimal(10 + index),
            ),
            ingestion_batch_id=batch_id,
            is_complete=True,
        )
        for index in range(3)
    )
    return build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
    )


def _stored_evidence(
    run_id,
    result,
    *,
    is_active: bool,
) -> StoredIntradayFeatureRunEvidence:
    return StoredIntradayFeatureRunEvidence(
        feature_run_id=run_id,
        pipeline_version=result.pipeline_version,
        source_data_hash=result.source_data_hash,
        source_provenance_hash=result.source_provenance_hash,
        registry_hash=result.registry_hash,
        result_hash=result.result_hash,
        feature_value_count=len(result.values),
        persisted_value_count=len(result.values),
        source_membership_count=len(result.source_ingestion_batch_ids),
        value_membership_count=len(result.values),
        dependency_membership_count=len(result.dependency_memberships),
        canonical_value_count=len(result.values),
        is_active=is_active,
    )


def _persistence_result(
    timeframe,
    result,
    *,
    sequence: int,
    inserted: int,
) -> IntradayFeaturePersistenceResult:
    return IntradayFeaturePersistenceResult(
        feature_run_id=UUID(
            f"00000000-0000-0000-0000-{_minutes(timeframe):04d}{sequence:08d}"
        ),
        pipeline_version=result.pipeline_version,
        timeframe=timeframe.value,
        source_data_hash=result.source_data_hash,
        source_provenance_hash=result.source_provenance_hash,
        registry_hash=result.registry_hash,
        result_hash=result.result_hash,
        source_candle_count=3,
        source_batch_count=1,
        computed_value_count=len(result.values),
        inserted_value_count=inserted,
        reused_value_count=len(result.values) - inserted,
        membership_count=len(result.values),
        dependency_membership_count=len(result.dependency_memberships),
        is_active=True,
    )


def _minutes(timeframe: CandleTimeframe) -> int:
    return int(timeframe_duration(timeframe).total_seconds() // 60)


if __name__ == "__main__":
    unittest.main()
