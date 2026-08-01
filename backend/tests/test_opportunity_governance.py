"""Focused Phase 4.7 tests for validation, health, and audit behavior."""

from datetime import timedelta
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.opportunity_intelligence.api import create_opportunity_intelligence_app
from app.opportunity_intelligence.audit import log_pipeline_result
from app.opportunity_intelligence.domain import LifecycleEvent, LifecycleState
from app.opportunity_intelligence.orchestration import (
    PipelineOutcome,
    PipelineRunResult,
    PipelineStage,
    PipelineStageRecord,
    PipelineStageStatus,
)
from app.opportunity_intelligence.repositories import ContractViolationError
from app.opportunity_intelligence.validation import (
    validate_contract_model,
    validate_lifecycle_transition,
    verify_provenance,
)
from tests.test_opportunity_domain_models import (
    AVAILABLE,
    _audit,
    _context,
    _feature_snapshot,
    _lifecycle,
    _market_snapshot,
    _policy,
)


AS_OF = "2025-01-01T00:05:01Z"


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class OpportunityGovernanceTests(unittest.TestCase):
    def test_contract_and_provenance_validation_are_fail_closed(self) -> None:
        market = _market_snapshot()

        self.assertIs(validate_contract_model(market, type(market)), market)
        self.assertIs(verify_provenance(market), market)
        with self.assertRaises(ContractViolationError):
            validate_contract_model("invalid")  # type: ignore[arg-type]
        with self.assertRaises(ContractViolationError):
            verify_provenance(market.candles[0])

    def test_lifecycle_successor_requires_identity_sequence_and_predecessor(self) -> None:
        lifecycle = _lifecycle()
        prior = lifecycle.events[-1]
        event = LifecycleEvent(
            contract_version="1.0.0",
            event_id="lifecycle.event.2",
            opportunity_id=lifecycle.opportunity_id,
            opportunity_version_id="opportunity.1.v1",
            prior_state=LifecycleState.DETECTED,
            resulting_state=LifecycleState.QUALIFIED,
            sequence=2,
            policy=_policy("policy.lifecycle"),
            reason_code="qualification.complete",
            occurred_at=AVAILABLE + timedelta(seconds=1),
            available_at=AVAILABLE + timedelta(seconds=1),
            assessment_reference=prior.assessment_reference,
            evidence_references=(prior.assessment_reference,),
            predecessor_event_id=prior.event_id,
            successor_opportunity_version_id=None,
            audit=_audit(prior.assessment_reference),
        )

        self.assertIs(validate_lifecycle_transition(lifecycle, event), event)
        conflicting = LifecycleEvent(
            contract_version="1.0.0",
            event_id="lifecycle.event.other",
            opportunity_id="opportunity.other",
            opportunity_version_id="opportunity.other.v1",
            prior_state=LifecycleState.DETECTED,
            resulting_state=LifecycleState.QUALIFIED,
            sequence=2,
            policy=event.policy,
            reason_code=event.reason_code,
            occurred_at=event.occurred_at,
            available_at=event.available_at,
            assessment_reference=event.assessment_reference,
            evidence_references=event.evidence_references,
            predecessor_event_id=event.predecessor_event_id,
            successor_opportunity_version_id=None,
            audit=event.audit,
        )
        with self.assertRaises(ContractViolationError):
            validate_lifecycle_transition(lifecycle, conflicting)

    def test_health_endpoint_fails_closed_without_governance_record(self) -> None:
        dashboard = SimpleNamespace(get_latest=AsyncMock())
        detail = SimpleNamespace(get_current=AsyncMock())
        client = TestClient(
            create_opportunity_intelligence_app(
                dashboard,  # type: ignore[arg-type]
                detail,  # type: ignore[arg-type]
            )
        )

        response = client.get(
            "/api/v1/opportunity-intelligence/health",
            params={
                "instrument": "BTC/USD",
                "timeframe": "5m",
                "as_of": AS_OF,
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "storage.unavailable")

    def test_pipeline_audit_log_contains_only_stable_trace_summary(self) -> None:
        market = _market_snapshot()
        features = _feature_snapshot()
        context = _context()
        attempt = SimpleNamespace(attempt_id="attempt.1")
        stage = PipelineStageRecord(
            sequence=1,
            stage=PipelineStage.MARKET_SNAPSHOT,
            status=PipelineStageStatus.COMPLETED,
            artifact_ids=(market.snapshot_id,),
        )
        result = PipelineRunResult(
            run_id="pipeline.run.audit",
            outcome=PipelineOutcome.NO_CANDIDATE,
            stages=(stage,),
            trace_hash="a" * 64,
            market_snapshot=market,
            feature_snapshot=features,
            market_context=context,
            detection_attempt=attempt,  # type: ignore[arg-type]
        )
        logger = logging.Logger("opportunity-audit-test")
        handler = _CaptureHandler()
        logger.addHandler(handler)

        log_pipeline_result(logger, result)

        self.assertEqual(len(handler.records), 1)
        record = handler.records[0]
        self.assertEqual(record.pipeline_run_id, result.run_id)
        self.assertEqual(record.pipeline_trace_hash, result.trace_hash)
        self.assertEqual(record.pipeline_stages, ("MARKET_SNAPSHOT",))


if __name__ == "__main__":
    unittest.main()
