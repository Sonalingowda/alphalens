"""P1-06 deterministic historical freshness and adequacy tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.market_data.coverage import (
    CoverageBatchEvidence,
    CoverageObservation,
    build_historical_coverage_snapshot,
)
from app.market_data.history import TEN_MINUTE_DERIVATION
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.quality import (
    APPROVED_ACQUISITION_ADEQUACY_POLICY,
    MINIMUM_ELAPSED_HISTORY_SECONDS,
    HistoricalQualityError,
    build_historical_quality_report,
    evaluate_acquisition_adequacy,
    verify_historical_quality_report,
)
from app.market_data.synchronization import CoverageSnapshotReference
from app.persistence.models import (
    HistoricalQualityReportRecord,
    HistoricalQualityTimeframeRecord,
)
from app.persistence.quality import (
    _report_record,
    persist_historical_quality_report,
)


_START = datetime(2025, 8, 1, 12, 0, tzinfo=timezone.utc)
_AS_OF = datetime(2026, 8, 1, 12, 7, tzinfo=timezone.utc)


class HistoricalQualityTests(unittest.TestCase):
    def test_exact_approved_adequacy_boundary_passes(self) -> None:
        status, outcome, ratio = evaluate_acquisition_adequacy(
            elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS,
            expected_candle_count=200,
            observed_candle_count=199,
        )

        self.assertEqual(status, "ADEQUATE")
        self.assertEqual(
            outcome,
            "ADEQUATE_FOR_DOWNSTREAM_ADEQUACY_EVALUATION",
        )
        self.assertEqual(ratio, Decimal("0.995000000000000000"))

    def test_below_approved_boundaries_is_inadequate(self) -> None:
        coverage_status, coverage_outcome, _ = evaluate_acquisition_adequacy(
            elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS - 1,
            expected_candle_count=200,
            observed_candle_count=200,
        )
        continuity_status, continuity_outcome, ratio = evaluate_acquisition_adequacy(
            elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS,
            expected_candle_count=200,
            observed_candle_count=198,
        )

        self.assertEqual(
            (coverage_status, coverage_outcome),
            ("INADEQUATE", "INADEQUATE_COVERAGE"),
        )
        self.assertEqual(
            (continuity_status, continuity_outcome),
            ("INADEQUATE", "INADEQUATE_CONTINUITY"),
        )
        self.assertEqual(ratio, Decimal("0.990000000000000000"))

    def test_current_open_candle_fails_closed(self) -> None:
        as_of = datetime(2026, 8, 1, 12, 7, tzinfo=timezone.utc)
        reference = _reference(
            CandleTimeframe.MINUTE_5,
            (
                datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 12, 5, tzinfo=timezone.utc),
            ),
            retrieved_at=datetime(2026, 8, 1, 12, 6, tzinfo=timezone.utc),
        )

        with self.assertRaisesRegex(
            HistoricalQualityError,
            "incomplete candle",
        ):
            _report(five=reference, as_of=as_of)

    def test_gap_and_provider_limited_start_are_reported_exactly(self) -> None:
        start = datetime(2026, 8, 1, 11, 45, tzinfo=timezone.utc)
        reference = _reference(
            CandleTimeframe.MINUTE_5,
            (start, start + timedelta(minutes=10)),
            retrieved_at=start + timedelta(minutes=16),
            provider_limit_reached=True,
        )

        report = _report(five=reference, as_of=start + timedelta(minutes=20))
        item = report.timeframes[0]

        self.assertEqual(item.gap_count, 1)
        self.assertEqual(
            item.gap_timestamps,
            (start + timedelta(minutes=5),),
        )
        self.assertEqual(item.expected_candle_count, 3)
        self.assertEqual(item.observed_candle_count, 2)
        self.assertEqual(item.coverage_ratio, Decimal("0.666666666666666667"))
        self.assertEqual(item.provider_limited_start, start)

    def test_stale_latest_candle_reports_lag_without_threshold(self) -> None:
        start = datetime(2026, 8, 1, 11, 45, tzinfo=timezone.utc)
        reference = _reference(
            CandleTimeframe.MINUTE_5,
            (start, start + timedelta(minutes=5)),
            retrieved_at=start + timedelta(minutes=11),
        )

        report = _report(five=reference, as_of=_AS_OF)
        item = report.timeframes[0]

        self.assertEqual(
            item.expected_latest_completed_timestamp,
            datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(item.canonical_lag_seconds, 600)
        self.assertEqual(item.retrieval_age_seconds, 660)
        self.assertEqual(item.freshness_status, "POLICY_UNAVAILABLE")
        self.assertFalse(report.publication_allowed)

    def test_each_timeframe_is_measured_independently(self) -> None:
        five = _reference(
            CandleTimeframe.MINUTE_5,
            (
                datetime(2026, 8, 1, 11, 55, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            ),
            retrieved_at=datetime(2026, 8, 1, 12, 6, tzinfo=timezone.utc),
        )
        ten = _reference(
            CandleTimeframe.MINUTE_10,
            (
                datetime(2026, 8, 1, 11, 40, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 11, 50, tzinfo=timezone.utc),
            ),
            retrieved_at=datetime(2026, 8, 1, 12, 1, tzinfo=timezone.utc),
        )
        fifteen = _reference(
            CandleTimeframe.MINUTE_15,
            (
                datetime(2026, 8, 1, 11, 30, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 11, 45, tzinfo=timezone.utc),
            ),
            retrieved_at=datetime(2026, 8, 1, 12, 2, tzinfo=timezone.utc),
        )

        report = _report(five=five, ten=ten, fifteen=fifteen)

        self.assertEqual(
            tuple(item.timeframe.value for item in report.timeframes),
            ("5m", "10m", "15m"),
        )
        self.assertEqual(
            tuple(
                item.expected_latest_completed_timestamp for item in report.timeframes
            ),
            (
                datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 11, 50, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 11, 45, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            tuple(item.retrieval_age_seconds for item in report.timeframes),
            (60, 360, 300),
        )

    def test_source_and_policy_unavailable_are_distinct(self) -> None:
        report = _report()

        self.assertEqual(
            tuple(item.adequacy_status for item in report.timeframes),
            ("SOURCE_UNAVAILABLE",) * 3,
        )
        self.assertEqual(
            tuple(item.acquisition_outcome for item in report.timeframes),
            ("SOURCE_UNAVAILABLE",) * 3,
        )
        self.assertEqual(report.freshness_policy_status, "POLICY_UNAVAILABLE")
        self.assertFalse(report.publication_allowed)

    def test_policy_version_mismatch_fails_closed(self) -> None:
        unsupported = replace(
            APPROVED_ACQUISITION_ADEQUACY_POLICY,
            version="2.0.0",
        )

        with self.assertRaisesRegex(
            HistoricalQualityError,
            "policy identifier, version, or values are unsupported",
        ):
            evaluate_acquisition_adequacy(
                elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS,
                expected_candle_count=200,
                observed_candle_count=199,
                policy=unsupported,
            )

    def test_report_is_deterministic_and_hash_tampering_fails(self) -> None:
        five = _reference(
            CandleTimeframe.MINUTE_5,
            (
                datetime(2026, 8, 1, 11, 55, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            ),
            retrieved_at=datetime(2026, 8, 1, 12, 6, tzinfo=timezone.utc),
        )
        first = _report(five=five)
        second = _report(five=five)

        self.assertEqual(first, second)
        self.assertEqual(len(first.acquisition_policy_hash), 64)
        self.assertEqual(len(first.source_provenance_hash), 64)
        self.assertEqual(len(first.result_hash), 64)
        verify_historical_quality_report(first)
        with self.assertRaisesRegex(
            HistoricalQualityError,
            "integrity verification failed",
        ):
            verify_historical_quality_report(replace(first, result_hash="0" * 64))

    def test_unresolved_conflict_fails_adequacy_closed(self) -> None:
        status, outcome, ratio = evaluate_acquisition_adequacy(
            elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS,
            expected_candle_count=200,
            observed_candle_count=200,
            unresolved_conflict_count=1,
        )

        self.assertEqual(status, "UNAVAILABLE")
        self.assertEqual(outcome, "UNRESOLVED_CONFLICT")
        self.assertEqual(ratio, Decimal("1.000000000000000000"))

    def test_schema_and_migration_are_immutable(self) -> None:
        self.assertEqual(
            HistoricalQualityReportRecord.__table__.name,
            "historical_quality_reports",
        )
        self.assertEqual(
            tuple(
                HistoricalQualityTimeframeRecord.__table__.primary_key.columns.keys()
            ),
            ("report_id", "timeframe"),
        )
        migration_path = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20260802_0032_create_historical_quality_reports.py"
        )
        spec = importlib.util.spec_from_file_location(
            "historical_quality_migration",
            migration_path,
        )
        if spec is None or spec.loader is None:
            self.fail("Historical quality migration could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mocked_op = MagicMock()
        with patch.object(module, "op", mocked_op):
            module.upgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.create_table.call_args_list],
            ["historical_quality_reports", "historical_quality_timeframes"],
        )
        mocked_op.reset_mock()
        with patch.object(module, "op", mocked_op):
            module.downgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.drop_table.call_args_list],
            ["historical_quality_timeframes", "historical_quality_reports"],
        )
        self.assertEqual(module.down_revision, "20260801_0031")


class HistoricalQualityPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_report_is_reused_after_verification(self) -> None:
        report = _report()
        created_session = _FakeSession()

        created = await persist_historical_quality_report(created_session, report)

        self.assertFalse(created.reused)
        self.assertEqual(created_session.flush_count, 1)
        self.assertEqual(len(created_session.added_groups[0]), 3)
        existing = _report_record(created.report_id, report)
        rows = created_session.added_groups[0]
        repeated = await persist_historical_quality_report(
            _FakeSession(existing, rows),
            report,
        )
        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.report_id, created.report_id)

    async def test_stored_report_corruption_fails_closed(self) -> None:
        report = _report()
        existing = _report_record(
            UUID("00000000-0000-0000-0000-000000000899"),
            report,
        )
        existing.source_provenance_hash = "f" * 64

        with self.assertRaisesRegex(
            HistoricalQualityError,
            "conflicts with its result hash",
        ):
            await persist_historical_quality_report(
                _FakeSession(existing, []),
                report,
            )


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class _FakeSession:
    def __init__(
        self,
        existing: HistoricalQualityReportRecord | None = None,
        rows: list[object] | None = None,
    ) -> None:
        self.existing = existing
        self.rows = rows or []
        self.added: list[object] = []
        self.added_groups: list[list[object]] = []
        self.flush_count = 0

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def scalar(self, statement):
        del statement
        return self.existing

    async def scalars(self, statement):
        del statement
        return _FakeScalarResult(self.rows)

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values) -> None:
        self.added_groups.append(list(values))

    async def flush(self) -> None:
        self.flush_count += 1


def _report(
    *,
    five: CoverageSnapshotReference | None = None,
    ten: CoverageSnapshotReference | None = None,
    fifteen: CoverageSnapshotReference | None = None,
    as_of: datetime = _AS_OF,
):
    return build_historical_quality_report(
        as_of=as_of,
        five_minute=five,
        ten_minute=ten,
        fifteen_minute=fifteen,
    )


def _reference(
    timeframe: CandleTimeframe,
    timestamps: tuple[datetime, ...],
    *,
    retrieved_at: datetime,
    provider_limit_reached: bool = False,
) -> CoverageSnapshotReference:
    duration = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]
    batch_id = {
        CandleTimeframe.MINUTE_5: UUID("00000000-0000-0000-0000-000000000801"),
        CandleTimeframe.MINUTE_10: UUID("00000000-0000-0000-0000-000000000802"),
        CandleTimeframe.MINUTE_15: UUID("00000000-0000-0000-0000-000000000803"),
    }[timeframe]
    observations = tuple(
        CoverageObservation(
            candle_id=index + 1,
            ingestion_batch_id=batch_id,
            provider="kraken",
            is_complete=True,
            candle=_candle(timestamp),
        )
        for index, timestamp in enumerate(timestamps)
    )
    derivation = timeframe is CandleTimeframe.MINUTE_10
    batch = CoverageBatchEvidence(
        ingestion_batch_id=batch_id,
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=timestamps[0],
        requested_end_exclusive=timestamps[-1] + duration,
        retrieved_at=retrieved_at,
        validation_passed=True,
        validation_issues=(),
        source_timeframe=(CandleTimeframe.MINUTE_5 if derivation else None),
        derivation_method=(TEN_MINUTE_DERIVATION if derivation else None),
        source_ingestion_batch_id=(
            UUID("00000000-0000-0000-0000-000000000801") if derivation else None
        ),
        provider_limit_reached=provider_limit_reached,
        available_range_start=timestamps[0],
        available_range_end=timestamps[-1],
    )
    snapshot = build_historical_coverage_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
        batches=(batch,),
    )
    snapshot_id = UUID(
        {
            CandleTimeframe.MINUTE_5: "00000000-0000-0000-0000-000000000811",
            CandleTimeframe.MINUTE_10: "00000000-0000-0000-0000-000000000812",
            CandleTimeframe.MINUTE_15: "00000000-0000-0000-0000-000000000813",
        }[timeframe]
    )
    return CoverageSnapshotReference(snapshot_id=snapshot_id, snapshot=snapshot)


def _candle(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal("100.000000000000000001"),
        high=Decimal("102.000000000000000001"),
        low=Decimal("99.000000000000000001"),
        close=Decimal("101.000000000000000001"),
        volume=Decimal("1.123456789012345678"),
    )


if __name__ == "__main__":
    unittest.main()
