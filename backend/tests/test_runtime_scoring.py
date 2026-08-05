"""Tests for Runtime Scoring Policy v1.0."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import PolicyReference
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineExecutionError,
)
from app.opportunity_intelligence.persistence import (
    EvidenceMemoryRepository,
    MarketContextMemoryRepository,
    OpportunityMemoryRepository,
    QualificationMemoryRepository,
    ScoringMemoryRepository,
)
from app.opportunity_intelligence.repositories import StorageUnavailableError
from app.opportunity_intelligence.services import (
    PolicyUnavailableError,
    ServiceContractError,
    ServiceUnavailableError,
)
from app.runtime_qualification import RuntimeQualificationService
from app.runtime_scoring import (
    RUNTIME_SCORING_POLICY_HASH,
    RUNTIME_SCORING_POLICY_ID,
    RUNTIME_SCORING_POLICY_VERSION,
    RuntimeScoringService,
)
from tests.test_runtime_assessment import _assessment_fixture, _request


class RuntimeScoringServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_scoring_persists_limited_ordinal_score(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()

        score = await service.score(
            opportunity,
            qualification,
            evidence,
            fixture.context,
        )

        self.assertEqual(score.policy.policy_id, RUNTIME_SCORING_POLICY_ID)
        self.assertEqual(score.policy.policy_version, RUNTIME_SCORING_POLICY_VERSION)
        self.assertEqual(score.policy.integrity_digest, RUNTIME_SCORING_POLICY_HASH)
        self.assertEqual(score.aggregate_value, 50)
        self.assertEqual(score.components[0].component_id, "opportunity_quality")
        self.assertEqual(
            score.components[0].limitations[-3:],
            (
                "scoring.risk_unavailable",
                "scoring.confidence_unavailable",
                "scoring.reward_unavailable",
            ),
        )
        self.assertEqual(len(scores._records), 1)

    async def test_missing_opportunity_is_unavailable(self) -> None:
        fixture, opportunity, qualification, evidence, _, scores = await _fixture()
        service = _service(
            opportunities=OpportunityMemoryRepository(),
            qualifications=QualificationMemoryRepository(),
            evidence=EvidenceMemoryRepository(),
            market_contexts=MarketContextMemoryRepository(),
            scores=scores,
        )

        with self.assertRaises(ServiceUnavailableError):
            await service.score(opportunity, qualification, evidence, fixture.context)
        self.assertEqual(len(scores._records), 0)

    async def test_missing_qualification_is_unavailable(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()
        service = _service(
            opportunities=service._opportunities,
            qualifications=QualificationMemoryRepository(),
            evidence=service._evidence,
            market_contexts=service._market_contexts,
            scores=scores,
        )

        with self.assertRaises(ServiceUnavailableError):
            await service.score(opportunity, qualification, evidence, fixture.context)
        self.assertEqual(len(scores._records), 0)

    async def test_missing_evidence_is_unavailable(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()
        service = _service(
            opportunities=service._opportunities,
            qualifications=service._qualifications,
            evidence=EvidenceMemoryRepository(),
            market_contexts=service._market_contexts,
            scores=scores,
        )

        with self.assertRaises(ServiceUnavailableError):
            await service.score(opportunity, qualification, evidence, fixture.context)
        self.assertEqual(len(scores._records), 0)

    async def test_invalid_lineage_is_rejected(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()
        invalid = replace(evidence, candidate_id="candidate.invalid")

        with self.assertRaises(ServiceContractError):
            await service.score(opportunity, qualification, invalid, fixture.context)
        self.assertEqual(len(scores._records), 0)

    async def test_stale_lineage_artifact_is_unavailable(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()
        stale_context = replace(
            fixture.context,
            audit=replace(
                fixture.context.audit,
                available_at=qualification.audit.evidence_cutoff + timedelta(seconds=1),
            ),
        )
        contexts = MarketContextMemoryRepository()
        await contexts.save(stale_context)
        service = _service(
            opportunities=service._opportunities,
            qualifications=service._qualifications,
            evidence=service._evidence,
            market_contexts=contexts,
            scores=scores,
        )

        with self.assertRaises(ServiceUnavailableError):
            await service.score(opportunity, qualification, evidence, stale_context)
        self.assertEqual(len(scores._records), 0)

    async def test_duplicate_execution_is_idempotent(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()

        first = await service.score(
            opportunity, qualification, evidence, fixture.context
        )
        second = await service.score(
            opportunity, qualification, evidence, fixture.context
        )

        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(len(scores._records), 1)

    async def test_repository_failure_propagates_without_partial_score(self) -> None:
        fixture, opportunity, qualification, evidence, service, _ = await _fixture()
        failing = SimpleNamespace(
            save=AsyncMock(side_effect=StorageUnavailableError("score down"))
        )
        service = _service(
            opportunities=service._opportunities,
            qualifications=service._qualifications,
            evidence=service._evidence,
            market_contexts=service._market_contexts,
            scores=failing,
        )

        with self.assertRaises(StorageUnavailableError):
            await service.score(opportunity, qualification, evidence, fixture.context)

    async def test_policy_blocked_fails_closed(self) -> None:
        (
            fixture,
            opportunity,
            qualification,
            evidence,
            service,
            scores,
        ) = await _fixture()
        service = _service(
            opportunities=service._opportunities,
            qualifications=service._qualifications,
            evidence=service._evidence,
            market_contexts=service._market_contexts,
            scores=scores,
            policy=PolicyReference("other_policy", "1.0.0", "0" * 64),
        )

        with self.assertRaises(PolicyUnavailableError):
            await service.score(opportunity, qualification, evidence, fixture.context)
        self.assertEqual(len(scores._records), 0)

    async def test_pipeline_hands_score_to_injected_ranking_service(self) -> None:
        fixture, opportunity, qualification, evidence, service, _ = await _fixture()
        ranking = SimpleNamespace(rank=AsyncMock(side_effect=RuntimeError("stop")))
        pipeline = OpportunityIntelligencePipeline(
            market_scanner=SimpleNamespace(scan=AsyncMock(return_value=fixture.market)),
            feature_snapshots=SimpleNamespace(
                resolve=AsyncMock(return_value=fixture.feature)
            ),
            market_contexts=SimpleNamespace(
                build=AsyncMock(return_value=fixture.context)
            ),
            detection=fixture.detector,
            evidence=fixture.service,
            assessment=fixture.assessment,
            qualification=fixture.qualification_service,
            scoring=service,
            ranking=ranking,
            lifecycle=SimpleNamespace(advance=AsyncMock()),
            notifications=SimpleNamespace(create_intents=AsyncMock()),
            dashboard=SimpleNamespace(project=AsyncMock()),
            indicators=SimpleNamespace(project=AsyncMock()),
            explanation=SimpleNamespace(explain=AsyncMock()),
            detail=SimpleNamespace(project=AsyncMock()),
        )

        with self.assertRaises(PipelineExecutionError):
            await pipeline.run(_request(fixture))

        ranking.rank.assert_awaited_once()
        call = ranking.rank.await_args.args
        self.assertEqual(
            call[0][0].opportunity_version_id, opportunity.opportunity_version_id
        )
        self.assertEqual(call[1][0].qualification_id, qualification.qualification_id)
        self.assertEqual(call[2][0].aggregate_value, 50)


async def _fixture():
    fixture, assessment, evidence, opportunities = await _assessment_fixture(
        "101.000000000000000000",
        "100.000000000000000000",
        "55.000000000000000000",
    )
    opportunity = await assessment.assess(fixture.candidate, evidence, fixture.context)
    qualifications = QualificationMemoryRepository()
    qualification_service = RuntimeQualificationService(
        opportunities=opportunities,
        evidence=fixture.evidence,
        market_contexts=fixture.contexts,
        feature_snapshots=fixture.features,
        market_snapshots=fixture.markets,
        qualifications=qualifications,
        code_version="git:runtimescoring100",
    )
    qualification = await qualification_service.qualify(
        opportunity,
        evidence,
        fixture.context,
    )
    scores = ScoringMemoryRepository()
    service = _service(
        opportunities=opportunities,
        qualifications=qualifications,
        evidence=fixture.evidence,
        market_contexts=fixture.contexts,
        scores=scores,
    )
    fixture.assessment = assessment
    fixture.qualification_service = qualification_service
    return fixture, opportunity, qualification, evidence, service, scores


def _service(
    *,
    opportunities,
    qualifications,
    evidence,
    market_contexts,
    scores,
    policy=None,
):
    return RuntimeScoringService(
        opportunities=opportunities,
        qualifications=qualifications,
        evidence=evidence,
        market_contexts=market_contexts,
        scores=scores,
        code_version="git:runtimescoring100",
        policy=policy,
    )
