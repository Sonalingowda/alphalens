"""P1-08 immutable historical expansion readiness validation tests."""

from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from app.historical_readiness import execute_historical_expansion_validation
from app.market_data.coverage import (
    ACQUISITION_POLICY_IDENTIFIER,
    ACQUISITION_POLICY_VERSION,
)
from app.market_data.inspection import build_historical_operational_inspection
from app.market_data.orchestration import ACQUISITION_POLICY_HASH
from app.market_data.quality import (
    CANDIDATE_C_ACQUISITION_POLICY_IDENTIFIER,
    CANDIDATE_C_ACQUISITION_POLICY_VERSION,
    approved_acquisition_adequacy_policy_hash,
)
from app.market_data.readiness import (
    BLOCKED_STATUS,
    READY_STATUS,
    HistoricalReadinessError,
    build_historical_expansion_readiness_report,
    verify_historical_expansion_readiness_report,
)
from app.persistence.models import HistoricalExpansionReadinessReportRecord
from app.persistence.readiness import (
    HistoricalReadinessPersistenceResult,
    _record,
    load_historical_expansion_readiness_report,
    persist_historical_expansion_readiness_report,
)


_AS_OF = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
_AS_OF_TEXT = "2026-08-01T12:00:00.000000Z"
_HASHES = tuple(f"{value:x}" * 64 for value in range(1, 16))


class HistoricalReadinessTests(unittest.TestCase):
    def test_complete_verified_evidence_is_acquisition_eligible(self) -> None:
        report = build_historical_expansion_readiness_report(_inspection())
        payload = report.response()

        self.assertEqual(payload["readiness_status"], READY_STATUS)
        self.assertTrue(payload["acquisition_level_eligible"])
        self.assertFalse(payload["phase_2_authorized"])
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(
            [item["timeframe"] for item in payload["timeframes"]],
            ["5m", "10m", "15m"],
        )
        self.assertEqual(
            payload["source_membership_manifest"]["derivation_count"],
            2,
        )
        self.assertEqual(payload["acquisition"][0]["excluded_incomplete_count"], 1)
        self.assertEqual(len(report.result_hash), 64)
        verify_historical_expansion_readiness_report(report)

    def test_repeated_execution_is_byte_identical(self) -> None:
        first = build_historical_expansion_readiness_report(_inspection())
        second = build_historical_expansion_readiness_report(_inspection())

        self.assertEqual(first, second)
        self.assertEqual(first.canonical_json, second.canonical_json)

    def test_missing_evidence_produces_honest_immutable_blockers(self) -> None:
        inspection = build_historical_operational_inspection(
            as_of=_AS_OF,
            acquisition=[
                _acquisition("5m", available=False),
                _acquisition("15m", available=False),
            ],
            source_conflicts=[],
            synchronized_coverage=None,
            historical_quality=None,
        )

        report = build_historical_expansion_readiness_report(inspection)
        payload = report.response()

        self.assertEqual(payload["readiness_status"], BLOCKED_STATUS)
        self.assertFalse(payload["acquisition_level_eligible"])
        self.assertIn("SYNCHRONIZATION_UNAVAILABLE", payload["blockers"])
        self.assertIn("QUALITY_UNAVAILABLE", payload["blockers"])
        self.assertIn("POLICY_INCOMPATIBLE", payload["blockers"])
        self.assertFalse(payload["phase_2_authorized"])

    def test_conflict_and_inadequate_timeframe_block_readiness(self) -> None:
        source = _inspection().response()
        source.pop("result_hash")
        source["source_conflicts"] = [
            {
                "conflict_id": str(UUID(int=90)),
                "timeframe": "5m",
                "candle_timestamp": _AS_OF_TEXT,
                "available_at": _AS_OF_TEXT,
                "conflict_hash": _HASHES[0],
            }
        ]
        source["historical_quality"]["timeframes"][1][
            "adequacy_status"
        ] = "INADEQUATE"
        source["historical_quality"]["timeframes"][1][
            "acquisition_outcome"
        ] = "INADEQUATE_CONTINUITY"
        source["historical_quality"]["timeframes"][1][
            "observed_candle_count"
        ] = 1
        source["historical_quality"]["timeframes"][1]["gap_count"] = 1
        source["historical_quality"]["timeframes"][1]["gap_timestamps"] = [
            "2026-07-01T12:00:00.000000Z"
        ]
        source["historical_quality"]["timeframes"][1][
            "coverage_ratio"
        ] = "0.500000000000000000"
        source["synchronized_coverage"]["source_snapshots"][1][
            "observed_candle_count"
        ] = 1
        source["synchronized_coverage"]["source_snapshots"][1]["gap_count"] = 1
        inspection = _rebuild(source)

        payload = build_historical_expansion_readiness_report(inspection).response()

        self.assertIn("UNRESOLVED_SOURCE_CONFLICT", payload["blockers"])
        self.assertIn("QUALITY_10M_INADEQUATE", payload["blockers"])
        self.assertEqual(payload["readiness_status"], BLOCKED_STATUS)

    def test_policy_mismatch_and_provenance_divergence_block(self) -> None:
        source = _inspection().response()
        source.pop("result_hash")
        source["historical_quality"]["acquisition_policy_version"] = "2.0.0"
        source["historical_quality"]["timeframes"][2][
            "source_snapshot_result_hash"
        ] = _HASHES[14]

        payload = build_historical_expansion_readiness_report(
            _rebuild(source)
        ).response()

        self.assertIn("POLICY_INCOMPATIBLE", payload["blockers"])
        self.assertIn("PROVENANCE_15M_DIVERGENCE", payload["blockers"])

    def test_malformed_membership_and_corrupt_hash_fail_closed(self) -> None:
        source = _inspection().response()
        source.pop("result_hash")
        source["synchronized_coverage"]["derivations"][0]["source_members"] = [
            source["synchronized_coverage"]["derivations"][0]["source_members"][0]
        ]

        with self.assertRaisesRegex(HistoricalReadinessError, "exactly two"):
            build_historical_expansion_readiness_report(_rebuild(source))

        valid = _inspection()
        corrupted = replace(valid, result_hash="f" * 64)
        with self.assertRaisesRegex(HistoricalReadinessError, "hash"):
            build_historical_expansion_readiness_report(corrupted)

    def test_report_tampering_is_detected(self) -> None:
        report = build_historical_expansion_readiness_report(_inspection())
        payload = json.loads(report.canonical_json)
        payload["phase_2_authorized"] = True
        tampered = replace(
            report,
            canonical_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        )

        with self.assertRaises(HistoricalReadinessError):
            verify_historical_expansion_readiness_report(tampered)


class HistoricalReadinessPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_is_insert_once_and_idempotent(self) -> None:
        report = build_historical_expansion_readiness_report(_inspection())
        created_session = _FakeSession()

        created = await persist_historical_expansion_readiness_report(
            created_session,
            report,
        )

        self.assertFalse(created.reused)
        self.assertEqual(created_session.flush_count, 1)
        self.assertEqual(len(created_session.added), 1)
        existing = _record(created.report_id, report)
        repeated_session = _FakeSession(existing)
        repeated = await persist_historical_expansion_readiness_report(
            repeated_session,
            report,
        )
        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.report_id, created.report_id)
        self.assertEqual(repeated_session.added, [])

    async def test_stored_report_corruption_fails_closed(self) -> None:
        report = build_historical_expansion_readiness_report(_inspection())
        existing = _record(UUID(int=99), report)
        existing.source_provenance_hash = "f" * 64

        with self.assertRaisesRegex(HistoricalReadinessError, "conflicts"):
            await persist_historical_expansion_readiness_report(
                _FakeSession(existing),
                report,
            )

    async def test_persisted_report_round_trip_verifies_provenance(self) -> None:
        report = build_historical_expansion_readiness_report(_inspection())
        report_id = UUID(int=101)
        existing = _record(report_id, report)

        loaded = await load_historical_expansion_readiness_report(
            _FakeSession(existing),
            report_id,
        )

        self.assertEqual(loaded, report)
        self.assertEqual(
            loaded.response()["source_evidence"]["inspection_result_hash"],
            _inspection().result_hash,
        )


class HistoricalReadinessRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_reads_inspection_then_persists_report(self) -> None:
        sessions = _SessionMaker()
        persistence = HistoricalReadinessPersistenceResult(
            report_id=UUID(int=100),
            result_hash="f" * 64,
            reused=False,
        )
        with (
            patch(
                "app.historical_readiness.load_historical_operational_inspection",
                AsyncMock(return_value=_inspection()),
            ) as loader,
            patch(
                "app.historical_readiness.persist_historical_expansion_readiness_report",
                AsyncMock(return_value=persistence),
            ) as writer,
        ):
            execution = await execute_historical_expansion_validation(
                sessions,  # type: ignore[arg-type]
                as_of=_AS_OF,
            )

        self.assertEqual(sessions.calls, 2)
        loader.assert_awaited_once_with(sessions.values[0], as_of=_AS_OF)
        writer.assert_awaited_once_with(sessions.values[1], execution.report)
        self.assertEqual(execution.report.response()["readiness_status"], READY_STATUS)

    def test_runner_cannot_acquire_repair_or_enter_later_phases(self) -> None:
        source = inspect.getsource(
            __import__("app.historical_readiness", fromlist=["historical_readiness"])
        )
        forbidden = (
            "fetch_btc",
            "orchestrate_intraday",
            "MarketDataProvider",
            "features",
            "labels",
            "dataset",
        )
        self.assertTrue(all(value not in source for value in forbidden))

    def test_migration_is_single_append_only_table(self) -> None:
        migration_path = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20260802_0033_create_historical_readiness_reports.py"
        )
        spec = importlib.util.spec_from_file_location(
            "historical_readiness_migration",
            migration_path,
        )
        if spec is None or spec.loader is None:
            self.fail("Historical readiness migration could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mocked_op = MagicMock()

        with patch.object(module, "op", mocked_op):
            module.upgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.create_table.call_args_list],
            ["historical_expansion_readiness_reports"],
        )
        mocked_op.reset_mock()
        with patch.object(module, "op", mocked_op):
            module.downgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.drop_table.call_args_list],
            ["historical_expansion_readiness_reports"],
        )
        self.assertEqual(module.down_revision, "20260802_0032")


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeSession:
    def __init__(
        self,
        existing: HistoricalExpansionReadinessReportRecord | None = None,
    ) -> None:
        self.existing = existing
        self.added: list[object] = []
        self.flush_count = 0

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def scalar(self, statement):
        del statement
        return self.existing

    async def get(self, model, identity):
        del model, identity
        return self.existing

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1


class _SessionContext:
    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _SessionMaker:
    def __init__(self) -> None:
        self.calls = 0
        self.values: list[object] = []

    def __call__(self) -> _SessionContext:
        self.calls += 1
        value = object()
        self.values.append(value)
        return _SessionContext(value)


def _inspection():
    snapshots = [_snapshot(timeframe, index) for index, timeframe in enumerate(("5m", "10m", "15m"))]
    quality_timeframes = [
        _quality_timeframe(snapshot, index)
        for index, snapshot in enumerate(snapshots)
    ]
    return build_historical_operational_inspection(
        as_of=_AS_OF,
        acquisition=[_acquisition("5m"), _acquisition("15m")],
        source_conflicts=[],
        synchronized_coverage={
            "synchronization_id": str(UUID(int=50)),
            "as_of": _AS_OF_TEXT,
            "integrity_status": "VERIFIED",
            "source_snapshots": snapshots,
            "derivations": [_derivation(10, 0), _derivation(20, 1)],
            "differences": {
                "unpaired_five_minute_timestamps": [],
                "missing_native_fifteen_minute_timestamps": [],
                "native_fifteen_minute_without_complete_five_minute": [],
            },
            "source_provenance_hash": _HASHES[10],
            "result_hash": _HASHES[11],
        },
        historical_quality={
            "report_id": str(UUID(int=60)),
            "as_of": _AS_OF_TEXT,
            "integrity_status": "VERIFIED",
            "acquisition_policy_identifier": (
                CANDIDATE_C_ACQUISITION_POLICY_IDENTIFIER
            ),
            "acquisition_policy_version": CANDIDATE_C_ACQUISITION_POLICY_VERSION,
            "acquisition_policy_hash": approved_acquisition_adequacy_policy_hash(),
            "source_policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
            "source_policy_version": ACQUISITION_POLICY_VERSION,
            "freshness_policy_status": "POLICY_UNAVAILABLE",
            "publication_allowed": False,
            "timeframes": quality_timeframes,
            "source_provenance_hash": _HASHES[12],
            "result_hash": _HASHES[13],
        },
    )


def _rebuild(source: dict):
    return build_historical_operational_inspection(
        as_of=_AS_OF,
        acquisition=source["acquisition"],
        source_conflicts=source["source_conflicts"],
        synchronized_coverage=source["synchronized_coverage"],
        historical_quality=source["historical_quality"],
    )


def _acquisition(timeframe: str, *, available: bool = True) -> dict:
    if not available:
        return {
            "timeframe": timeframe,
            "operational_state": "NO_ATTEMPT",
            "attempt": None,
            "outcome": None,
            "checkpoint": None,
            "integrity_status": "UNAVAILABLE",
        }
    return {
        "timeframe": timeframe,
        "operational_state": "SUCCESS_REUSE_ONLY",
        "attempt": {
            "attempt_hash": _HASHES[0],
            "code_version": "test-code-version",
            "configuration_hash": _HASHES[1],
            "policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
            "policy_version": ACQUISITION_POLICY_VERSION,
            "policy_hash": ACQUISITION_POLICY_HASH,
        },
        "outcome": {"terminal_reason": "SUCCESS_REUSE_ONLY"},
        "checkpoint": {
            "timeframe": timeframe,
            "checkpoint_hash": _HASHES[2],
            "progress_hash": _HASHES[3],
            "source_data_hash": _HASHES[4],
            "provider_available_start": "2025-08-01T12:00:00.000000Z",
            "provider_available_end": _AS_OF_TEXT,
            "provider_row_count": 3,
            "accepted_count": 2,
            "excluded_incomplete_count": 1,
            "reused_count": 2,
            "inserted_count": 0,
            "validation_passed": True,
            "provider_limit_reached": True,
        },
        "integrity_status": "VERIFIED",
    }


def _snapshot(timeframe: str, index: int) -> dict:
    return {
        "timeframe": timeframe,
        "snapshot_id": str(UUID(int=70 + index)),
        "coverage_range_start": "2025-08-01T12:00:00.000000Z",
        "coverage_range_end": _AS_OF_TEXT,
        "expected_candle_count": 2,
        "observed_candle_count": 2,
        "gap_count": 0,
        "source_data_hash": _HASHES[5 + index],
        "source_provenance_hash": _HASHES[6 + index],
        "result_hash": _HASHES[7 + index],
    }


def _quality_timeframe(snapshot: dict, index: int) -> dict:
    return {
        "timeframe": snapshot["timeframe"],
        "adequacy_status": "ADEQUATE",
        "acquisition_outcome": "ADEQUATE_FOR_DOWNSTREAM_ADEQUACY_EVALUATION",
        "source_snapshot_id": snapshot["snapshot_id"],
        "source_snapshot_result_hash": snapshot["result_hash"],
        "source_provenance_hash": snapshot["source_provenance_hash"],
        "elapsed_history_seconds": 365 * 24 * 60 * 60,
        "expected_candle_count": snapshot["expected_candle_count"],
        "observed_candle_count": snapshot["observed_candle_count"],
        "gap_count": snapshot["gap_count"],
        "gap_timestamps": [],
        "coverage_ratio": "1.000000000000000000",
        "unresolved_conflict_count": 0,
        "validation_verified": True,
        "provenance_verified": True,
        "result_hash": _HASHES[9 + index],
    }


def _derivation(candle_id: int, index: int) -> dict:
    return {
        "derived_candle_id": candle_id,
        "source_membership_hash": _HASHES[1 + index],
        "result_hash": _HASHES[2 + index],
        "source_members": [
            {"ordinal": 0, "candle_hash": _HASHES[3 + index]},
            {"ordinal": 1, "candle_hash": _HASHES[4 + index]},
        ],
    }
