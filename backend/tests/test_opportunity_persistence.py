"""Focused Phase 4.5 tests for immutable repository implementations."""

from dataclasses import replace
from datetime import timedelta
import unittest

from app.opportunity_intelligence.domain import CandidateAttemptState, DetectionAttempt
from app.opportunity_intelligence.persistence import (
    DashboardProjectionMemoryRepository,
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    ExplanationMemoryRepository,
    FeatureSnapshotMemoryRepository,
    LifecycleMemoryRepository,
    MarketContextMemoryRepository,
    MarketSnapshotMemoryRepository,
    NotificationMemoryRepository,
    OpportunityDetailMemoryRepository,
    OpportunityMemoryRepository,
    OpportunityPlanMemoryRepository,
    QualificationMemoryRepository,
    RankingMemoryRepository,
    RuntimeGovernanceMemoryRepository,
    ScoringMemoryRepository,
)
from app.opportunity_intelligence.repositories import (
    ContractViolationError,
    DuplicateEntityError,
    EntityAsOfQuery,
    EntityId,
    EntityNotFoundError,
    MarketSnapshotRepository,
    RepositoryListQuery,
    ScopedRepositoryQuery,
)
from tests.test_opportunity_domain_models import (
    AVAILABLE,
    SCOPE,
    _audit,
    _candidate,
    _market_snapshot,
    _policy,
    _reference,
)


IMPLEMENTATIONS = (
    MarketSnapshotMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    OpportunityMemoryRepository,
    QualificationMemoryRepository,
    ScoringMemoryRepository,
    RankingMemoryRepository,
    OpportunityPlanMemoryRepository,
    LifecycleMemoryRepository,
    NotificationMemoryRepository,
    DashboardProjectionMemoryRepository,
    OpportunityDetailMemoryRepository,
    ExplanationMemoryRepository,
    RuntimeGovernanceMemoryRepository,
)


def _detected_attempt() -> DetectionAttempt:
    source = _reference("detection.input")
    return DetectionAttempt(
        contract_version="1.0.0",
        attempt_id="attempt.1",
        scope=SCOPE,
        state=CandidateAttemptState.DETECTED,
        detection_policy=_policy("policy.detection"),
        input_references=(source,),
        reason_codes=("candidate.detected",),
        candidate_id="candidate.1",
        audit=_audit(source),
    )


class OpportunityPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def test_all_required_repository_implementations_are_public(self) -> None:
        self.assertEqual(len(IMPLEMENTATIONS), 16)
        self.assertIsInstance(MarketSnapshotMemoryRepository(), MarketSnapshotRepository)

    async def test_save_is_idempotent_and_conflicting_content_fails(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        snapshot = _market_snapshot()

        first = await repository.save(snapshot)
        second = await repository.save(snapshot)

        self.assertIs(first, snapshot)
        self.assertIs(second, snapshot)
        conflicting = replace(
            snapshot,
            audit=replace(snapshot.audit, result_hash="b" * 64),
        )
        with self.assertRaises(DuplicateEntityError):
            await repository.save(conflicting)

    async def test_batch_failure_is_atomic(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        first = _market_snapshot()
        conflicting = replace(
            first,
            audit=replace(first.audit, result_hash="b" * 64),
        )

        with self.assertRaises(DuplicateEntityError):
            await repository.save_batch((first, conflicting))

        with self.assertRaises(EntityNotFoundError):
            await repository.get_by_id(EntityId(first.snapshot_id))

    async def test_as_of_scope_and_pagination_are_deterministic(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        first = _market_snapshot()
        second = replace(
            first,
            snapshot_id="market.snapshot.2",
            audit=replace(
                first.audit,
                created_at=AVAILABLE + timedelta(seconds=1),
                available_at=AVAILABLE + timedelta(seconds=1),
            ),
        )
        await repository.save_batch((first, second))

        before_second = await repository.get_latest(
            ScopedRepositoryQuery(scope=SCOPE, as_of=AVAILABLE, limit=1)
        )
        page_one = await repository.list(
            RepositoryListQuery(
                as_of=AVAILABLE + timedelta(seconds=1),
                limit=1,
                scope=SCOPE,
            )
        )
        page_two = await repository.list(
            RepositoryListQuery(
                as_of=AVAILABLE + timedelta(seconds=1),
                limit=1,
                scope=SCOPE,
                cursor=page_one.next_cursor,
            )
        )

        self.assertEqual(before_second.snapshot_id, first.snapshot_id)
        self.assertEqual(page_one.items, (second,))
        self.assertEqual(page_two.items, (first,))
        self.assertIsNone(page_two.next_cursor)

    async def test_detection_requires_matching_attempt(self) -> None:
        repository = DetectionMemoryRepository()
        candidate = _candidate()

        with self.assertRaises(ContractViolationError):
            await repository.save_candidate(candidate)

        await repository.save_attempt(_detected_attempt())
        self.assertEqual(await repository.save_candidate(candidate), candidate)
        self.assertTrue(
            await repository.candidate_exists(
                EntityAsOfQuery(EntityId(candidate.candidate_id), AVAILABLE)
            )
        )

    async def test_invalid_runtime_argument_fails_closed(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        with self.assertRaises(Exception) as captured:
            await repository.save("not-a-snapshot")  # type: ignore[arg-type]
        self.assertIsInstance(captured.exception, ContractViolationError)


if __name__ == "__main__":
    unittest.main()
