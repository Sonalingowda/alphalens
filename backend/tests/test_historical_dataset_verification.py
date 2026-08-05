"""Focused integration tests for the read-only historical verification CLI."""

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from app.historical_dataset_verification import (
    HistoricalDatasetVerificationReport,
    build_historical_dataset_verification_report,
    execute_historical_dataset_verification,
    main,
    verify_historical_dataset_verification_report,
)
from app.market_data.readiness import HistoricalExpansionReadinessReport


_AS_OF = "2026-08-01T12:00:00.000000Z"
_HASH = "a" * 64


class HistoricalDatasetVerificationReportTests(TestCase):
    def test_report_is_deterministic_and_hash_verified(self) -> None:
        with patch(
            "app.historical_dataset_verification.verify_historical_expansion_readiness_report"
        ):
            first = build_historical_dataset_verification_report(_readiness())
            second = build_historical_dataset_verification_report(_readiness())

        self.assertEqual(first, second)
        self.assertEqual(first.response()["verification_status"], "PASSED")
        verify_historical_dataset_verification_report(first)

    def test_blocked_readiness_returns_a_failed_verification_report(self) -> None:
        with patch(
            "app.historical_dataset_verification.verify_historical_expansion_readiness_report"
        ):
            report = build_historical_dataset_verification_report(
                _readiness(blockers=["COVERAGE_5M_GAP"])
            )

        self.assertEqual(report.response()["verification_status"], "FAILED")
        self.assertEqual(report.response()["failure_reasons"], ["COVERAGE_5M_GAP"])

    def test_tampering_fails_closed(self) -> None:
        with patch(
            "app.historical_dataset_verification.verify_historical_expansion_readiness_report"
        ):
            report = build_historical_dataset_verification_report(_readiness())

        with self.assertRaisesRegex(Exception, "hash"):
            verify_historical_dataset_verification_report(
                replace(report, result_hash="0" * 64)
            )


class HistoricalDatasetVerificationExecutionTests(IsolatedAsyncioTestCase):
    async def test_execution_reads_once_and_never_persists(self) -> None:
        session_maker = _SessionMaker()
        inspection = object()
        readiness = _readiness()
        with (
            patch(
                "app.historical_dataset_verification.load_historical_operational_inspection",
                AsyncMock(return_value=inspection),
            ) as loader,
            patch(
                "app.historical_dataset_verification.build_historical_expansion_readiness_report",
                return_value=readiness,
            ) as builder,
            patch(
                "app.historical_dataset_verification.verify_historical_expansion_readiness_report"
            ),
        ):
            report = await execute_historical_dataset_verification(
                session_maker,  # type: ignore[arg-type]
                as_of=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(report.response()["verification_status"], "PASSED")
        self.assertEqual(session_maker.calls, 1)
        loader.assert_awaited_once_with(
            session_maker.session,
            as_of=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        )
        builder.assert_called_once_with(inspection)


class HistoricalDatasetVerificationCliTests(TestCase):
    def test_cli_returns_zero_for_verified_evidence(self) -> None:
        with patch(
            "app.historical_dataset_verification.execute_historical_dataset_verification",
            AsyncMock(return_value=_verification_report("PASSED")),
        ):
            self.assertEqual(main(["--as-of", "2026-08-01T12:00:00Z"]), 0)

    def test_cli_returns_nonzero_for_failed_evidence(self) -> None:
        with patch(
            "app.historical_dataset_verification.execute_historical_dataset_verification",
            AsyncMock(return_value=_verification_report("FAILED")),
        ):
            self.assertEqual(main(["--as-of", "2026-08-01T12:00:00Z"]), 1)


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _SessionMaker:
    def __init__(self) -> None:
        self.calls = 0
        self.session = _Session()

    def __call__(self):
        self.calls += 1
        return self.session


def _readiness(blockers: list[str] | None = None) -> HistoricalExpansionReadinessReport:
    failure_reasons = blockers or []
    payload = {
        "schema_version": "1.0.0",
        "hash_schema_version": "1.0.0",
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "as_of": _AS_OF,
        "readiness_status": (
            "READY_FOR_DOWNSTREAM_ADEQUACY_EVALUATION" if not failure_reasons else "BLOCKED"
        ),
        "acquisition_level_eligible": not failure_reasons,
        "phase_2_authorized": False,
        "blockers": failure_reasons,
        "checks": [],
        "timeframes": [],
        "source_evidence": {
            "inspection_result_hash": _HASH,
        },
        "source_provenance_hash": _HASH,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return HistoricalExpansionReadinessReport(
        canonical_json=canonical,
        result_hash=sha256(canonical.encode("utf-8")).hexdigest(),
    )


def _verification_report(status: str) -> HistoricalDatasetVerificationReport:
    failures = [] if status == "PASSED" else ["COVERAGE_5M_GAP"]
    payload = {
        "schema_version": "1.0.0",
        "hash_schema_version": "1.0.0",
        "report_type": "historical_dataset_verification",
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "as_of": _AS_OF,
        "verification_status": status,
        "failure_reasons": failures,
        "checks": [],
        "timeframes": [],
        "source_evidence": {
            "readiness_result_hash": _HASH,
            "inspection_result_hash": _HASH,
            "source_provenance_hash": _HASH,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return HistoricalDatasetVerificationReport(
        canonical_json=canonical,
        result_hash=sha256(canonical.encode("utf-8")).hexdigest(),
    )
