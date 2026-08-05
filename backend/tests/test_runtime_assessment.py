"""Tests for Assessment Policy v1.0.1."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import PolicyReference
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineExecutionError,
    PipelineOutcome,
    PipelineRunRequest,
)
from app.opportunity_intelligence.persistence import (
    EvidenceMemoryRepository,
    OpportunityMemoryRepository,
)
from app.opportunity_intelligence.repositories import (
    ScopedRepositoryQuery,
    StorageUnavailableError,
)
from app.opportunity_intelligence.services import (
    OpportunityAssessmentService,
    PolicyUnavailableError,
    ServiceContractError,
    ServiceUnavailableError,
)
from app.runtime_assessment import (
    RUNTIME_ASSESSMENT_POLICY_HASH,
    RUNTIME_ASSESSMENT_POLICY_ID,
    RUNTIME_ASSESSMENT_POLICY_VERSION,
    RuntimeAssessmentService,
)
from tests.test_opportunity_domain_models import CUTOFF
from tests.test_runtime_evidence import _fixture


class RuntimeAssessmentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_buy_assessment_persists_deterministic_opportunity(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )

        opportunity = await service.assess(fixture.candidate, evidence, fixture.context)

        self.assertIsInstance(service, OpportunityAssessmentService)
        self.assertEqual(opportunity.stance.value, "BUY")
        self.assertEqual(
            opportunity.decision_policy.policy_id,
            RUNTIME_ASSESSMENT_POLICY_ID,
        )
        self.assertEqual(
            opportunity.decision_policy.policy_version,
            RUNTIME_ASSESSMENT_POLICY_VERSION,
        )
        self.assertEqual(
            opportunity.decision_policy.integrity_digest,
            RUNTIME_ASSESSMENT_POLICY_HASH,
        )
        self.assertEqual(
            opportunity.reason_codes[-1], "assessment.buy_direction_confirmed"
        )
        self.assertEqual(len(opportunities._records), 1)

    async def test_sell_assessment_persists_sell_opportunity(self) -> None:
        fixture, service, evidence, _ = await _assessment_fixture(
            "99.000000000000000000",
            "100.000000000000000000",
            "45.000000000000000000",
        )

        opportunity = await service.assess(fixture.candidate, evidence, fixture.context)

        self.assertEqual(opportunity.stance.value, "SELL")
        self.assertEqual(
            opportunity.reason_codes[-1], "assessment.sell_direction_confirmed"
        )

    async def test_missing_evidence_is_unavailable_without_opportunity(self) -> None:
        fixture, _, evidence, _ = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        opportunities = OpportunityMemoryRepository()
        service = _service(
            fixture, evidence=EvidenceMemoryRepository(), opportunities=opportunities
        )

        with self.assertRaises(ServiceUnavailableError):
            await service.assess(fixture.candidate, evidence, fixture.context)
        self.assertEqual(len(opportunities._records), 0)

    async def test_stale_context_is_unavailable_without_opportunity(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        stale_observation = replace(
            fixture.context.data_quality.observations[0],
            time_end=CUTOFF,
        )
        stale_context = replace(
            fixture.context,
            context_id="market.context.stale",
            data_quality=replace(
                fixture.context.data_quality,
                observations=(stale_observation,),
            ),
        )
        await fixture.contexts.save(stale_context)

        with self.assertRaises(ServiceContractError):
            await service.assess(fixture.candidate, evidence, stale_context)
        self.assertEqual(len(opportunities._records), 0)

    async def test_lineage_failure_is_contract_unavailable(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        invalid_evidence = replace(evidence, candidate_id="candidate.invalid")

        with self.assertRaises(ServiceContractError):
            await service.assess(fixture.candidate, invalid_evidence, fixture.context)
        self.assertEqual(len(opportunities._records), 0)

    async def test_policy_unavailable_fails_closed(self) -> None:
        fixture, _, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        service = _service(
            fixture,
            opportunities=opportunities,
            policy=PolicyReference("other_policy", "1.0.0", "0" * 64),
        )

        with self.assertRaises(PolicyUnavailableError):
            await service.assess(fixture.candidate, evidence, fixture.context)
        self.assertEqual(len(opportunities._records), 0)

    async def test_repository_failure_propagates_without_partial_opportunity(
        self,
    ) -> None:
        fixture, _, evidence, _ = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        failing = SimpleNamespace(
            save=AsyncMock(side_effect=StorageUnavailableError("opportunity down"))
        )
        service = _service(fixture, opportunities=failing)

        with self.assertRaises(StorageUnavailableError):
            await service.assess(fixture.candidate, evidence, fixture.context)

    async def test_duplicate_execution_is_idempotent(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )

        first = await service.assess(fixture.candidate, evidence, fixture.context)
        second = await service.assess(fixture.candidate, evidence, fixture.context)

        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(len(opportunities._records), 1)

    async def test_pipeline_returns_policy_blocked_at_assessment(self) -> None:
        fixture, _, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        assessment = _service(
            fixture,
            opportunities=opportunities,
            policy=PolicyReference("other_policy", "1.0.0", "0" * 64),
        )
        qualification = SimpleNamespace(qualify=AsyncMock())
        pipeline = _pipeline(fixture, assessment, qualification)

        result = await pipeline.run(_request(fixture))

        self.assertIs(result.outcome, PipelineOutcome.POLICY_BLOCKED)
        self.assertEqual(result.stages[-1].reason_code, "assessment.policy_unavailable")
        qualification.qualify.assert_not_awaited()

    async def test_pipeline_continues_to_injected_qualification_service(self) -> None:
        fixture, service, _, _ = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        qualification = SimpleNamespace(
            qualify=AsyncMock(side_effect=RuntimeError("qualification unavailable"))
        )
        pipeline = _pipeline(fixture, service, qualification)

        with self.assertRaises(PipelineExecutionError) as error:
            await pipeline.run(_request(fixture))
        self.assertEqual(error.exception.stage.value, "QUALIFICATION")
        qualification.qualify.assert_awaited_once()


async def _assessment_fixture(ema_12: str, ema_26: str, rsi: str):
    fixture = await _fixture(ema_12, ema_26, rsi)
    evidence = await fixture.service.assemble(
        fixture.candidate,
        fixture.market,
        fixture.feature,
        fixture.context,
    )
    opportunities = OpportunityMemoryRepository()
    return (
        fixture,
        _service(fixture, opportunities=opportunities),
        evidence,
        opportunities,
    )


def _service(
    fixture,
    *,
    evidence=None,
    opportunities=None,
    policy=None,
) -> RuntimeAssessmentService:
    return RuntimeAssessmentService(
        candidates=fixture.detections,
        evidence=evidence or fixture.evidence,
        market_snapshots=fixture.markets,
        feature_snapshots=fixture.features,
        market_contexts=fixture.contexts,
        opportunities=opportunities or OpportunityMemoryRepository(),
        code_version="git:runtimeassessment101",
        policy=policy,
    )


def _pipeline(fixture, assessment, qualification):
    return OpportunityIntelligencePipeline(
        market_scanner=SimpleNamespace(scan=AsyncMock(return_value=fixture.market)),
        feature_snapshots=SimpleNamespace(
            resolve=AsyncMock(return_value=fixture.feature)
        ),
        market_contexts=SimpleNamespace(build=AsyncMock(return_value=fixture.context)),
        detection=fixture.detector,
        evidence=fixture.service,
        assessment=assessment,
        qualification=qualification,
        scoring=SimpleNamespace(score=AsyncMock()),
        ranking=SimpleNamespace(rank=AsyncMock()),
        lifecycle=SimpleNamespace(advance=AsyncMock()),
        notifications=SimpleNamespace(create_intents=AsyncMock()),
        dashboard=SimpleNamespace(project=AsyncMock()),
        indicators=SimpleNamespace(project=AsyncMock()),
        explanation=SimpleNamespace(explain=AsyncMock()),
        detail=SimpleNamespace(project=AsyncMock()),
    )


def _request(fixture) -> PipelineRunRequest:
    return PipelineRunRequest(
        run_id="assessment.pipeline.run.1",
        query=ScopedRepositoryQuery(scope=fixture.market.scope, as_of=CUTOFF, limit=1),
    )
