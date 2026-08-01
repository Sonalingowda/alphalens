"""Focused Phase 4.4 tests for deterministic application orchestration."""

from datetime import timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import (
    CandidateAttemptState,
    DetectionAttempt,
    QualificationGateResult,
    QualificationOutcome,
    QualificationRecord,
    QualificationStatus,
)
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineExecutionError,
    PipelineOutcome,
    PipelineRunRequest,
    PipelineStage,
    PipelineStageStatus,
)
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.opportunity_intelligence.services import PolicyUnavailableError
from tests.test_opportunity_domain_models import (
    CUTOFF,
    SCOPE,
    _audit,
    _candidate,
    _context,
    _evidence_package,
    _feature_snapshot,
    _market_snapshot,
    _opportunity,
    _policy,
    _reference,
)


UTC = timezone.utc


def _attempt(
    state: CandidateAttemptState,
    candidate_id: str | None,
) -> DetectionAttempt:
    source = _reference("detection.input")
    return DetectionAttempt(
        contract_version="1.0.0",
        attempt_id="attempt.1",
        scope=SCOPE,
        state=state,
        detection_policy=_policy("policy.detection"),
        input_references=(source,),
        reason_codes=("detection.complete",),
        candidate_id=candidate_id,
        audit=_audit(source),
    )


def _qualification() -> QualificationRecord:
    evidence = _reference("qualification.evidence")
    return QualificationRecord(
        contract_version="1.0.0",
        qualification_id="qualification.1",
        assessment_reference=_reference("assessment.1"),
        context_reference=_reference("market.context.1"),
        evidence_package_reference=_reference("evidence.package.1"),
        policy=_policy("policy.qualification"),
        gate_results=(
            QualificationGateResult(
                gate_id="gate.integrity",
                requirement_class="mandatory",
                status=QualificationStatus.PASS,
                evidence_references=(evidence,),
                reason_code="integrity.valid",
            ),
        ),
        outcome=QualificationOutcome.QUALIFIED,
        exclusions=(),
        limitations=(),
        audit=_audit(
            _reference("assessment.1"),
            _reference("market.context.1"),
            _reference("evidence.package.1"),
        ),
    )


def _request() -> PipelineRunRequest:
    return PipelineRunRequest(
        run_id="pipeline.run.1",
        query=ScopedRepositoryQuery(scope=SCOPE, as_of=CUTOFF, limit=1),
    )


def _pipeline(**overrides: object) -> OpportunityIntelligencePipeline:
    defaults: dict[str, object] = {
        "market_scanner": SimpleNamespace(scan=AsyncMock(return_value=_market_snapshot())),
        "feature_snapshots": SimpleNamespace(
            resolve=AsyncMock(return_value=_feature_snapshot())
        ),
        "market_contexts": SimpleNamespace(build=AsyncMock(return_value=_context())),
        "detection": SimpleNamespace(
            detect=AsyncMock(
                return_value=(
                    _attempt(CandidateAttemptState.NOT_DETECTED, None),
                    None,
                )
            )
        ),
        "evidence": SimpleNamespace(assemble=AsyncMock()),
        "assessment": SimpleNamespace(assess=AsyncMock()),
        "qualification": SimpleNamespace(qualify=AsyncMock()),
        "scoring": SimpleNamespace(score=AsyncMock()),
        "ranking": SimpleNamespace(rank=AsyncMock()),
        "lifecycle": SimpleNamespace(advance=AsyncMock()),
        "notifications": SimpleNamespace(create_intents=AsyncMock()),
        "dashboard": SimpleNamespace(project=AsyncMock()),
        "indicators": SimpleNamespace(project=AsyncMock()),
        "explanation": SimpleNamespace(explain=AsyncMock()),
        "detail": SimpleNamespace(project=AsyncMock()),
    }
    defaults.update(overrides)
    return OpportunityIntelligencePipeline(**defaults)  # type: ignore[arg-type]


class OpportunityOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_candidate_stops_before_downstream_services(self) -> None:
        pipeline = _pipeline()

        first = await pipeline.run(_request())
        second = await pipeline.run(_request())

        self.assertIs(first.outcome, PipelineOutcome.NO_CANDIDATE)
        self.assertEqual(first.trace_hash, second.trace_hash)
        self.assertEqual(
            tuple(stage.stage for stage in first.stages),
            (
                PipelineStage.MARKET_SNAPSHOT,
                PipelineStage.FEATURE_SNAPSHOT,
                PipelineStage.MARKET_CONTEXT,
                PipelineStage.OPPORTUNITY_DETECTION,
            ),
        )
        pipeline.evidence.assemble.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_missing_scoring_policy_returns_explicit_gate(self) -> None:
        candidate = _candidate()
        pipeline = _pipeline(
            detection=SimpleNamespace(
                detect=AsyncMock(
                    return_value=(
                        _attempt(CandidateAttemptState.DETECTED, candidate.candidate_id),
                        candidate,
                    )
                )
            ),
            evidence=SimpleNamespace(
                assemble=AsyncMock(return_value=_evidence_package())
            ),
            assessment=SimpleNamespace(assess=AsyncMock(return_value=_opportunity())),
            qualification=SimpleNamespace(
                qualify=AsyncMock(return_value=_qualification())
            ),
            scoring=SimpleNamespace(
                score=AsyncMock(side_effect=PolicyUnavailableError("unapproved"))
            ),
        )

        result = await pipeline.run(_request())

        self.assertIs(result.outcome, PipelineOutcome.POLICY_BLOCKED)
        self.assertIs(result.stages[-1].stage, PipelineStage.SCORING)
        self.assertIs(result.stages[-1].status, PipelineStageStatus.BLOCKED)
        self.assertEqual(result.stages[-1].reason_code, "policy.unavailable")
        pipeline.ranking.rank.assert_not_awaited()  # type: ignore[attr-defined]

    async def test_service_failure_raises_with_partial_immutable_trace(self) -> None:
        pipeline = _pipeline(
            market_contexts=SimpleNamespace(
                build=AsyncMock(side_effect=RuntimeError("unexpected"))
            )
        )

        with self.assertRaises(PipelineExecutionError) as captured:
            await pipeline.run(_request())

        error = captured.exception
        self.assertIs(error.stage, PipelineStage.MARKET_CONTEXT)
        self.assertIs(error.stages[-1].status, PipelineStageStatus.BLOCKED)
        self.assertEqual(error.stages[-1].reason_code, "service.failure")
        self.assertEqual(len(error.trace_hash), 64)


if __name__ == "__main__":
    unittest.main()
