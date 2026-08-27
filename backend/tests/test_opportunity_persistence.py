"""Focused Phase 4.5 tests for immutable repository implementations."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from app.opportunity_intelligence.domain import (
    CandidateAttemptState,
    DetectionAttempt,
    MarketCandleSnapshot,
    MarketSnapshot,
)
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
    CUTOFF,
    SCOPE,
    START,
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

    async def test_transport_lineage_conflict_resolution(self) -> None:
        """WS-vs-REST transport lineage differences for same candle are resolved.

        When the same Binance candle arrives via both WebSocket (live) and REST
        (gap repair) paths, the transport metadata differs (source_payload_hash,
        event_time, lineage) but the market truth (OHLCV, timestamp) is identical.
        The repository should resolve this benign conflict by keeping the
        already-persisted canonical entity and NOT raising DuplicateEntityError.
        """
        from app.opportunity_intelligence.persistence import (
            MarketSnapshotPostgreSQLRepository,
        )
        from app.persistence.database import session_factory
        from app.opportunity_intelligence.domain import MarketSnapshot

        # This test requires a running PostgreSQL instance.
        # We'll test the equivalence logic directly via the repository method.
        repository = MarketSnapshotPostgreSQLRepository(session_factory)

        # Create a base market snapshot (simulating WS path)
        base_snapshot = _market_snapshot()

        # Create a conflicting snapshot with different transport lineage
        # (different source_payload_hash, event_time, but same market content)
        source_ws = _reference("candle.source.ws", available_at=START)
        source_rest = _reference("candle.source.rest", available_at=START)
        candle = MarketCandleSnapshot(
            candle_id="candle.1",
            timestamp=START,
            available_at=CUTOFF,
            open=Decimal("100.000000000000000000"),
            high=Decimal("110.000000000000000000"),
            low=Decimal("90.000000000000000000"),
            close=Decimal("105.000000000000000000"),
            volume=Decimal("10.000000000000000000"),
            source_reference=source_ws,
        )
        ws_snapshot = MarketSnapshot(
            contract_version="1.0.0",
            snapshot_id="market.snapshot.transport.test",
            scope=SCOPE,
            candles=(candle,),
            complete=True,
            audit=_audit(source_ws),
        )

        # Same market content, different transport lineage (REST path)
        candle_rest = MarketCandleSnapshot(
            candle_id="candle.1",
            timestamp=START,
            available_at=CUTOFF,
            open=Decimal("100.000000000000000000"),
            high=Decimal("110.000000000000000000"),
            low=Decimal("90.000000000000000000"),
            close=Decimal("105.000000000000000000"),
            volume=Decimal("10.000000000000000000"),
            source_reference=source_rest,  # Different source reference
        )
        rest_snapshot = MarketSnapshot(
            contract_version="1.0.0",
            snapshot_id="market.snapshot.transport.test",  # Same identity
            scope=SCOPE,
            candles=(candle_rest,),
            complete=True,
            audit=_audit(source_rest),  # Different audit (different source)
        )

        # Verify they have different canonical hashes (different transport lineage)
        self.assertNotEqual(
            ws_snapshot.canonical_sha256(),
            rest_snapshot.canonical_sha256(),
            "WS and REST snapshots must have different canonical hashes due to transport lineage",
        )

        # Verify market content is equivalent
        self.assertTrue(
            repository._equivalent_market_snapshot_content(ws_snapshot, rest_snapshot),
            "WS and REST snapshots must have equivalent market content",
        )

        # Test the equivalence method directly
        self.assertTrue(
            repository._equivalent_market_snapshot_content(ws_snapshot, ws_snapshot),
            "Snapshot must be equivalent to itself",
        )

        # Test that genuinely different market content is NOT equivalent
        different_candle = MarketCandleSnapshot(
            candle_id="candle.1",
            timestamp=START,
            available_at=CUTOFF,
            open=Decimal("100.000000000000000000"),
            high=Decimal("110.000000000000000000"),
            low=Decimal("90.000000000000000000"),
            close=Decimal("106.000000000000000000"),  # Different close price
            volume=Decimal("10.000000000000000000"),
            source_reference=source_ws,
        )
        different_snapshot = MarketSnapshot(
            contract_version="1.0.0",
            snapshot_id="market.snapshot.transport.test",
            scope=SCOPE,
            candles=(different_candle,),
            complete=True,
            audit=_audit(source_ws),
        )
        self.assertFalse(
            repository._equivalent_market_snapshot_content(ws_snapshot, different_snapshot),
            "Snapshots with different close prices must not be equivalent",
        )

        # Note: Full integration test with PostgreSQL requires running DB.
        # The above tests the equivalence logic which is the core of the fix.

    async def test_invalid_runtime_argument_fails_closed(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        with self.assertRaises(Exception) as captured:
            await repository.save("not-a-snapshot")  # type: ignore[arg-type]
        self.assertIsInstance(captured.exception, ContractViolationError)


if __name__ == "__main__":
    unittest.main()
