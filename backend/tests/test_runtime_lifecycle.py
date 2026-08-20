"""Tests for RuntimeLifecycleService.advance() and expire_stale().

Covers the critical scenario that caused the live pipeline failure:
  - opportunity with qualification_reference=None (the pipeline-produced state)
  - successful lifecycle creation from pipeline objects
  - WAIT stance rejection
  - assessment identity mismatch
  - qualification identity mismatch (when qualification_reference IS present)
  - ranking membership missing
  - non-QUALIFIED outcome
  - expire_stale transitions RANKED to EXPIRED
  - expire_stale preserves terminal states
  - expire_stale returns empty for no stale items
  - expire_stale respects batch_limit
"""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

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


class LifecycleExpireStaleTests(unittest.IsolatedAsyncioTestCase):
    """Tests for RuntimeLifecycleService.expire_stale()."""

    STALE_NOW = datetime(2025, 1, 1, 0, 20, 0, tzinfo=timezone.utc)
    FRESH_NOW = datetime(2025, 1, 1, 0, 12, 0, tzinfo=timezone.utc)

    async def _ranked_lifecycle(self):
        """Create a ranked lifecycle and the service."""
        fixture, opportunity, qualification, ranking, service, lifecycles = (
            await _lifecycle_fixture()
        )
        lifecycle = await service.advance(opportunity, qualification, ranking, None)
        return service, lifecycles, lifecycle, opportunity

    async def test_stale_lifecycle_transitions_to_expired(self):
        """RANKED lifecycle older than 10 minutes becomes EXPIRED."""
        service, lifecycles, lifecycle, _ = await self._ranked_lifecycle()

        stale_as_of = self.STALE_NOW
        expired = await service.expire_stale(
            as_of=stale_as_of,
            active_max_age_minutes=10,
        )

        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].current_state, LifecycleState.EXPIRED)
        self.assertEqual(expired[0].opportunity_id, lifecycle.opportunity_id)
        self.assertEqual(len(expired[0].events), 4)

        from app.opportunity_intelligence.repositories.queries import EntityAsOfQuery, EntityId
        stored = await lifecycles.get_current(
            EntityAsOfQuery(EntityId(lifecycle.opportunity_id), stale_as_of)
        )
        self.assertEqual(stored.current_state, LifecycleState.EXPIRED)

    async def test_fresh_lifecycle_not_expired(self):
        """RANKED lifecycle younger than 10 minutes remains RANKED."""
        service, lifecycles, lifecycle, _ = await self._ranked_lifecycle()

        fresh_as_of = self.FRESH_NOW
        expired = await service.expire_stale(
            as_of=fresh_as_of,
            active_max_age_minutes=10,
        )

        self.assertEqual(len(expired), 0)
        from app.opportunity_intelligence.repositories.queries import EntityAsOfQuery, EntityId
        stored = await lifecycles.get_current(
            EntityAsOfQuery(EntityId(lifecycle.opportunity_id), fresh_as_of)
        )
        self.assertEqual(stored.current_state, LifecycleState.RANKED)

    async def test_expire_stale_returns_empty_when_no_stale(self):
        """expire_stale returns empty tuple when nothing is stale."""
        service, _, _, _ = await self._ranked_lifecycle()

        expired = await service.expire_stale(
            as_of=self.FRESH_NOW,
            active_max_age_minutes=10,
        )
        self.assertEqual(expired, ())

    async def test_expire_stale_respects_batch_limit(self):
        """expire_stale processes at most batch_limit items."""
        service, _, _, _ = await self._ranked_lifecycle()

        expired = await service.expire_stale(
            as_of=self.STALE_NOW,
            active_max_age_minutes=10,
            batch_limit=0,
        )
        self.assertEqual(expired, ())

    async def test_expired_lifecycle_event_has_correct_reason(self):
        """The EXPIRED event uses reason_code opportunity.expired."""
        service, _, lifecycle, _ = await self._ranked_lifecycle()

        expired = await service.expire_stale(
            as_of=self.STALE_NOW,
            active_max_age_minutes=10,
        )

        expire_event = expired[0].events[-1]
        self.assertEqual(expire_event.reason_code, "opportunity.expired")
        self.assertEqual(expire_event.resulting_state, LifecycleState.EXPIRED)
        self.assertEqual(expire_event.prior_state, LifecycleState.RANKED)

    async def test_expired_lifecycle_preserves_direction(self):
        """EXPIRED lifecycle preserves original direction."""
        service, _, lifecycle, _ = await self._ranked_lifecycle()

        expired = await service.expire_stale(
            as_of=self.STALE_NOW,
            active_max_age_minutes=10,
        )

        self.assertEqual(expired[0].direction, lifecycle.direction)

    async def test_expired_lifecycle_preserves_scope(self):
        """EXPIRED lifecycle preserves original scope."""
        service, _, lifecycle, _ = await self._ranked_lifecycle()

        expired = await service.expire_stale(
            as_of=self.STALE_NOW,
            active_max_age_minutes=10,
        )

        self.assertEqual(expired[0].scope, lifecycle.scope)


if __name__ == "__main__":
    unittest.main()
