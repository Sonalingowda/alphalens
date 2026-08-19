"""Tests for RuntimeLifecycleService.advance().

Covers the critical scenario that caused the live pipeline failure:
  - opportunity with qualification_reference=None (the pipeline-produced state)
  - successful lifecycle creation from pipeline objects
  - WAIT stance rejection
  - assessment identity mismatch
  - qualification identity mismatch (when qualification_reference IS present)
  - ranking membership missing
  - non-QUALIFIED outcome
"""

import unittest
from dataclasses import replace

from app.opportunity_intelligence.domain import (
    IntegrityReference,
    LifecycleState,
    OpportunityStance,
    QualificationOutcome,
    QualificationStatus,
)
from app.opportunity_intelligence.persistence import (
    LifecycleMemoryRepository,
)
from app.opportunity_intelligence.services import ServiceContractError
from app.runtime_lifecycle import RuntimeLifecycleService
from tests.test_runtime_ranking import _ranking_fixture


async def _lifecycle_fixture(ema12="105", ema26="100", rsi="65"):
    """Build a complete fixture chain through ranking, returning lifecycle inputs."""
    fixture, assessment_service, opportunity, qualification, score, ranking_service, _ = (
        await _ranking_fixture(ema12, ema26, rsi)
    )

    ranking = await ranking_service.rank(
        (opportunity,), (qualification,), (score,), fixture.context.audit.available_at
    )

    lifecycles = LifecycleMemoryRepository()
    service = RuntimeLifecycleService(lifecycles=lifecycles)

    return fixture, opportunity, qualification, ranking, service, lifecycles


class RuntimeLifecycleServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_succeeds_with_qualification_reference_none(self) -> None:
        fixture, opportunity, qualification, ranking, service, lifecycles = (
            await _lifecycle_fixture()
        )

        self.assertIsNone(opportunity.qualification_reference)

        lifecycle = await service.advance(opportunity, qualification, ranking, None)

        self.assertIsNotNone(lifecycle)
        self.assertEqual(lifecycle.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(lifecycle.current_state, LifecycleState.RANKED)
        self.assertEqual(len(lifecycle.events), 3)
        self.assertEqual(lifecycle.events[0].resulting_state, LifecycleState.DETECTED)
        self.assertEqual(lifecycle.events[1].resulting_state, LifecycleState.QUALIFIED)
        self.assertEqual(lifecycle.events[2].resulting_state, LifecycleState.RANKED)

    async def test_lifecycle_events_are_persisted(self) -> None:
        fixture, opportunity, qualification, ranking, service, lifecycles = (
            await _lifecycle_fixture()
        )

        await service.advance(opportunity, qualification, ranking, None)

        events = [
            e for e in lifecycles._events._records.values()
            if e.opportunity_id == opportunity.opportunity_id
        ]
        self.assertEqual(len(events), 3)
        sequences = sorted(e.sequence for e in events)
        self.assertEqual(sequences, [1, 2, 3])

    async def test_wait_stance_raises_contract_error(self) -> None:
        fixture, opportunity, qualification, ranking, service, _ = (
            await _lifecycle_fixture()
        )
        wait_opportunity = replace(
            opportunity,
            stance=OpportunityStance.WAIT,
            qualification_reference=None,
            score_reference=None,
            plan=None,
        )

        with self.assertRaises(ServiceContractError):
            await service.advance(wait_opportunity, qualification, ranking, None)

    async def test_assessment_identity_mismatch_raises(self) -> None:
        fixture, opportunity, qualification, ranking, service, _ = (
            await _lifecycle_fixture()
        )
        wrong_qualification = replace(
            qualification,
            assessment_reference=IntegrityReference(
                artifact_id="wrong.opportunity_version_id",
                artifact_type="opportunity",
                artifact_version="1.0.0",
                integrity_digest="0" * 64,
                available_at=qualification.audit.available_at,
            ),
        )

        with self.assertRaises(ServiceContractError):
            await service.advance(opportunity, wrong_qualification, ranking, None)

    async def test_qualification_identity_mismatch_raises_when_reference_present(self) -> None:
        fixture, opportunity, qualification, ranking, service, _ = (
            await _lifecycle_fixture()
        )
        opp_with_ref = replace(
            opportunity,
            qualification_reference=IntegrityReference(
                artifact_id="wrong.qualification.id",
                artifact_type="qualification_record",
                artifact_version="1.0.0",
                integrity_digest="0" * 64,
                available_at=qualification.audit.available_at,
            ),
        )

        with self.assertRaises(ServiceContractError):
            await service.advance(opp_with_ref, qualification, ranking, None)

    async def test_ranking_membership_missing_raises(self) -> None:
        fixture, opportunity, qualification, ranking, service, _ = (
            await _lifecycle_fixture()
        )
        empty_ranking = replace(
            ranking,
            memberships=(),
            eligible_candidate_references=(),
            qualified_opportunity_references=(),
            candidate_set_hash="0" * 64,
        )

        with self.assertRaises(ServiceContractError):
            await service.advance(opportunity, qualification, empty_ranking, None)

    async def test_non_qualified_outcome_raises(self) -> None:
        fixture, opportunity, qualification, ranking, service, _ = (
            await _lifecycle_fixture()
        )
        failed_gate = replace(qualification.gate_results[0], status=QualificationStatus.FAIL)
        not_qualified = replace(
            qualification,
            outcome=QualificationOutcome.NOT_QUALIFIED,
            gate_results=(failed_gate, *qualification.gate_results[1:]),
        )

        with self.assertRaises(ServiceContractError):
            await service.advance(opportunity, not_qualified, ranking, None)


if __name__ == "__main__":
    unittest.main()
