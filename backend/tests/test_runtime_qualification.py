"""Tests for Runtime Qualification Policy v1.0."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import PolicyReference
from app.opportunity_intelligence.orchestration import PipelineOutcome
from app.opportunity_intelligence.persistence import (
    EvidenceMemoryRepository,
    OpportunityMemoryRepository,
    QualificationMemoryRepository,
)
from app.opportunity_intelligence.repositories import StorageUnavailableError
from app.opportunity_intelligence.services import (
    PolicyUnavailableError,
    ServiceContractError,
    ServiceUnavailableError,
)
from app.runtime_qualification import RuntimeQualificationService
from tests.test_runtime_assessment import _assessment_fixture, _pipeline, _request


class RuntimeQualificationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_buy_qualification_persists_qualified_record(self) -> None:
        fixture, opportunity, evidence, service, qualifications = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )

        record = await service.qualify(opportunity, evidence, fixture.context)

        self.assertEqual(record.outcome.value, "QUALIFIED")
        self.assertEqual(
            record.gate_results[-1].reason_code,
            "qualification.scope_chronology_verified",
        )
        self.assertEqual(len(qualifications._records), 1)

    async def test_sell_qualification_persists_qualified_record(self) -> None:
        fixture, opportunity, evidence, service, _ = await _fixture(
            "99.000000000000000000", "100.000000000000000000", "45.000000000000000000"
        )

        record = await service.qualify(opportunity, evidence, fixture.context)

        self.assertEqual(record.outcome.value, "QUALIFIED")

    async def test_policy_blocked(self) -> None:
        fixture, opportunity, evidence, _, qualifications = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _service(
            fixture,
            qualifications=qualifications,
            policy=PolicyReference("other_policy", "1.0.0", "0" * 64),
        )

        with self.assertRaises(PolicyUnavailableError):
            await service.qualify(opportunity, evidence, fixture.context)
        self.assertEqual(len(qualifications._records), 0)

    async def test_missing_opportunity_is_unavailable(self) -> None:
        fixture, opportunity, evidence, _, qualifications = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _service(fixture, opportunities=OpportunityMemoryRepository())

        with self.assertRaises(ServiceUnavailableError):
            await service.qualify(opportunity, evidence, fixture.context)
        self.assertEqual(len(qualifications._records), 0)

    async def test_missing_evidence_is_unavailable(self) -> None:
        fixture, opportunity, evidence, _, qualifications = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _service(
            fixture, evidence=EvidenceMemoryRepository(), qualifications=qualifications
        )

        with self.assertRaises(ServiceUnavailableError):
            await service.qualify(opportunity, evidence, fixture.context)

    async def test_lineage_failure_is_rejected(self) -> None:
        fixture, opportunity, evidence, service, _ = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        invalid = replace(evidence, candidate_id="candidate.invalid")

        with self.assertRaises(ServiceContractError):
            await service.qualify(opportunity, invalid, fixture.context)

    async def test_repository_failure_propagates(self) -> None:
        fixture, opportunity, evidence, service, _ = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        failing = SimpleNamespace(
            save=AsyncMock(side_effect=StorageUnavailableError("down"))
        )
        service = _service(
            fixture,
            opportunities=service._opportunities,
            qualifications=failing,
        )

        with self.assertRaises(StorageUnavailableError):
            await service.qualify(opportunity, evidence, fixture.context)

    async def test_duplicate_execution_is_idempotent(self) -> None:
        fixture, opportunity, evidence, service, qualifications = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )

        first = await service.qualify(opportunity, evidence, fixture.context)
        second = await service.qualify(opportunity, evidence, fixture.context)

        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(len(qualifications._records), 1)

    async def test_pipeline_policy_blocked_at_qualification_stops_scoring(self) -> None:
        fixture, assessment, _, opportunities = await _assessment_fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        qualification = _service(
            fixture,
            opportunities=opportunities,
            policy=PolicyReference("other_policy", "1.0.0", "0" * 64),
        )
        pipeline = _pipeline(
            fixture, assessment=assessment, qualification=qualification
        )

        result = await pipeline.run(_request(fixture))

        self.assertIs(result.outcome, PipelineOutcome.POLICY_BLOCKED)
        self.assertEqual(
            result.stages[-1].reason_code, "qualification.policy_unavailable"
        )


async def _fixture(ema_12: str, ema_26: str, rsi: str):
    fixture, assessment, evidence, opportunities = await _assessment_fixture(
        ema_12, ema_26, rsi
    )
    opportunity = await assessment.assess(fixture.candidate, evidence, fixture.context)
    qualifications = QualificationMemoryRepository()
    return (
        fixture,
        opportunity,
        evidence,
        _service(
            fixture,
            opportunities=opportunities,
            qualifications=qualifications,
        ),
        qualifications,
    )


def _service(
    fixture, *, opportunities=None, evidence=None, qualifications=None, policy=None
):
    return RuntimeQualificationService(
        opportunities=opportunities or OpportunityMemoryRepository(),
        evidence=evidence or fixture.evidence,
        market_contexts=fixture.contexts,
        feature_snapshots=fixture.features,
        market_snapshots=fixture.markets,
        qualifications=qualifications or QualificationMemoryRepository(),
        code_version="git:runtimequalification100",
        policy=policy,
    )
