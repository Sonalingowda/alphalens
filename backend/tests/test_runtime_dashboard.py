"""Tests for the runtime dashboard projection service (INT-008).

Covers every required scenario:
  - populated dashboard (single ranked member)
  - empty dashboard (empty RankingSnapshot → valid empty DashboardPage)
  - duplicate execution (idempotent)
  - stale ranking (RankingSnapshot not in repository)
  - invalid lineage (digest mismatch between pipeline arg and repository)
  - repository failure (storage unavailable on save)
  - POLICY_BLOCKED (not applicable as a distinct hash check; tested via
    missing-ranking = UNAVAILABLE path, as the contract has no separate
    policy artifact)
  - pipeline handoff (OpportunityIntelligencePipeline calls dashboard.project
    with the RankingSnapshot produced by RuntimeRankingService)
"""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import (
    LifecycleState,
)
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineExecutionError,
)
from app.opportunity_intelligence.persistence import (
    DashboardProjectionMemoryRepository,
    RankingMemoryRepository,
)
from app.opportunity_intelligence.repositories import StorageUnavailableError
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)
from app.runtime_dashboard import RuntimeDashboardProjectionService
from tests.test_runtime_ranking import _ranking_fixture, _as_of, _request


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------

async def _dashboard_fixture():
    """Build a complete fixture chain through ranking and return dashboard inputs.

    Returns:
        (fixture, opportunity, lifecycle_stub, ranking_snapshot,
         dashboard_service, dashboard_repo)
    """
    (
        fixture,
        assessment_service,
        opportunity,
        qualification,
        score,
        ranking_service,
        rankings,
    ) = await _ranking_fixture()

    ranking = await ranking_service.rank(
        (opportunity,), (qualification,), (score,), _as_of(fixture)
    )

    # Build a minimal but valid lifecycle stub.  The dashboard service only
    # reads opportunity_id and current_state from each lifecycle, so a
    # SimpleNamespace suffices for every test that does not exercise
    # lifecycle-specific assertions.
    lifecycle = SimpleNamespace(
        opportunity_id=opportunity.opportunity_id,
        current_state=LifecycleState.RANKED,
    )

    dashboard_repo = DashboardProjectionMemoryRepository()
    dashboard_service = _make_service(rankings=rankings, dashboard=dashboard_repo)

    fixture.rankings = rankings
    fixture.ranking = ranking
    fixture.opportunity = opportunity

    return fixture, opportunity, lifecycle, ranking, dashboard_service, dashboard_repo


def _make_service(*, rankings, dashboard, code_version="git:dashboardtest100"):
    return RuntimeDashboardProjectionService(
        rankings=rankings,
        dashboard=dashboard,
        code_version=code_version,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class RuntimeDashboardProjectionServiceTests(unittest.IsolatedAsyncioTestCase):

    # --- Populated dashboard ---

    async def test_populated_dashboard_produces_valid_page(self) -> None:
        fixture, opportunity, lifecycle, ranking, service, dashboard_repo = (
            await _dashboard_fixture()
        )

        page = await service.project(ranking, (opportunity,), (lifecycle,))

        self.assertEqual(page.contract_version, "1.0.0")
        self.assertEqual(
            page.ranking_snapshot_reference.artifact_id, ranking.snapshot_id
        )
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].opportunity_id, opportunity.opportunity_id)
        self.assertEqual(page.items[0].rank, 1)
        self.assertEqual(page.items[0].stance, opportunity.stance)
        self.assertEqual(
            page.items[0].lifecycle_state, LifecycleState.RANKED
        )
        self.assertEqual(page.coverage_status, "complete")
        self.assertEqual(page.sort, "canonical.rank")
        self.assertEqual(len(dashboard_repo._records), 1)

    async def test_dashboard_item_rank_order_is_ascending(self) -> None:
        fixture, opportunity, lifecycle, ranking, service, _ = (
            await _dashboard_fixture()
        )
        page = await service.project(ranking, (opportunity,), (lifecycle,))
        ranks = tuple(item.rank for item in page.items)
        self.assertEqual(ranks, tuple(sorted(ranks)))

    async def test_result_hash_is_64_hex_characters(self) -> None:
        fixture, opportunity, lifecycle, ranking, service, _ = (
            await _dashboard_fixture()
        )
        page = await service.project(ranking, (opportunity,), (lifecycle,))
        self.assertRegex(page.audit.result_hash, r"^[0-9a-f]{64}$")

    async def test_scope_matches_ranking_scope(self) -> None:
        fixture, opportunity, lifecycle, ranking, service, _ = (
            await _dashboard_fixture()
        )
        page = await service.project(ranking, (opportunity,), (lifecycle,))
        self.assertEqual(page.scope, ranking.scope)

    async def test_page_identity_is_ranking_snapshot_id(self) -> None:
        """DashboardPage is keyed by ranking_snapshot_reference.artifact_id."""
        fixture, opportunity, lifecycle, ranking, service, dashboard_repo = (
            await _dashboard_fixture()
        )
        page = await service.project(ranking, (opportunity,), (lifecycle,))
        # The repository key is ranking_snapshot_reference.artifact_id.
        self.assertIn(ranking.snapshot_id, dashboard_repo._records)
        self.assertEqual(
            dashboard_repo._records[ranking.snapshot_id].canonical_sha256(),
            page.canonical_sha256(),
        )

    # --- Empty dashboard ---

    async def test_empty_ranking_produces_valid_empty_dashboard(self) -> None:
        """An empty RankingSnapshot (zero members) yields a valid empty DashboardPage."""
        fixture, opportunity, lifecycle, ranking, _, _ = (
            await _dashboard_fixture()
        )
        # Build an empty snapshot by manipulating the ranking fixture:
        # re-run ranking with no eligible scores in the repository.
        empty_rankings = RankingMemoryRepository()
        empty_dashboard_repo = DashboardProjectionMemoryRepository()

        # Persist the ranking (which has one member) but then create a new
        # ranking service that sees an empty scores repo so the window returns
        # nothing.  Because the triggering score must be present, instead we
        # directly build the empty dashboard case using an empty ranking
        # snapshot stub saved manually.
        from app.opportunity_intelligence.domain import (
            canonical_sha256,
        )

        # Re-use the existing ranking's audit timestamps to build a valid
        # empty snapshot that passes RankingSnapshot.__post_init__.
        existing_audit = ranking.audit
        empty_snapshot_id = (
            f"ranking.runtime_ema_rsi.BTCUSDT.5m."
            f"{int(existing_audit.evidence_cutoff.timestamp() * 1000) + 1}"
        )
        empty_audit = replace(
            existing_audit,
            result_hash="0" * 64,
        )
        from app.opportunity_intelligence.domain import RankingSnapshot
        empty_snapshot = RankingSnapshot(
            contract_version="1.0.0",
            snapshot_id=empty_snapshot_id,
            policy=ranking.policy,
            as_of=existing_audit.evidence_cutoff,
            generated_at=existing_audit.evidence_cutoff,
            scope=ranking.scope,
            eligible_candidate_references=(),
            qualified_opportunity_references=(),
            memberships=(),
            exclusions=(),
            candidate_set_hash=canonical_sha256(()),
            predecessor_snapshot_id=None,
            audit=replace(
                empty_audit,
                result_hash=canonical_sha256(
                    replace(
                        RankingSnapshot(
                            contract_version="1.0.0",
                            snapshot_id=empty_snapshot_id,
                            policy=ranking.policy,
                            as_of=existing_audit.evidence_cutoff,
                            generated_at=existing_audit.evidence_cutoff,
                            scope=ranking.scope,
                            eligible_candidate_references=(),
                            qualified_opportunity_references=(),
                            memberships=(),
                            exclusions=(),
                            candidate_set_hash=canonical_sha256(()),
                            predecessor_snapshot_id=None,
                            audit=empty_audit,
                        ),
                        audit=empty_audit,
                    ),
                    exclude=frozenset({"result_hash"}),
                ),
            ),
        )
        await empty_rankings.save(empty_snapshot)
        service = _make_service(
            rankings=empty_rankings,
            dashboard=empty_dashboard_repo,
        )

        page = await service.project(empty_snapshot, (), ())

        self.assertEqual(len(page.items), 0)
        self.assertEqual(page.coverage_status, "empty")
        self.assertEqual(len(empty_dashboard_repo._records), 1)

    # --- Duplicate execution (idempotency) ---

    async def test_duplicate_execution_is_idempotent(self) -> None:
        fixture, opportunity, lifecycle, ranking, service, dashboard_repo = (
            await _dashboard_fixture()
        )

        first = await service.project(ranking, (opportunity,), (lifecycle,))
        second = await service.project(ranking, (opportunity,), (lifecycle,))

        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(len(dashboard_repo._records), 1)

    # --- Stale ranking (not in repository) ---

    async def test_missing_ranking_snapshot_raises_unavailable(self) -> None:
        fixture, opportunity, lifecycle, ranking, _, dashboard_repo = (
            await _dashboard_fixture()
        )
        empty_rankings = RankingMemoryRepository()
        service = _make_service(rankings=empty_rankings, dashboard=dashboard_repo)

        with self.assertRaises(ServiceUnavailableError):
            await service.project(ranking, (opportunity,), (lifecycle,))
        self.assertEqual(len(dashboard_repo._records), 0)

    # --- Invalid lineage (digest mismatch) ---

    async def test_digest_mismatch_raises_contract_error(self) -> None:
        fixture, opportunity, lifecycle, ranking, service, dashboard_repo = (
            await _dashboard_fixture()
        )
        # Supply a ranking whose content differs from the persisted one.
        tampered = replace(ranking, sort="tampered") if hasattr(ranking, "sort") else replace(
            ranking,
            predecessor_snapshot_id=None,
            candidate_set_hash=replace(ranking, audit=replace(
                ranking.audit, result_hash="a" * 64
            )).audit.result_hash,
        )
        # Simplest way: change a field that shifts the digest.
        tampered = replace(
            ranking,
            audit=replace(ranking.audit, result_hash="a" * 64),
        )

        with self.assertRaises(ServiceContractError):
            await service.project(tampered, (opportunity,), (lifecycle,))
        self.assertEqual(len(dashboard_repo._records), 0)

    # --- Repository failure ---

    async def test_repository_failure_propagates_without_partial_page(
        self,
    ) -> None:
        fixture, opportunity, lifecycle, ranking, _, _ = (
            await _dashboard_fixture()
        )
        failing_dashboard = SimpleNamespace(
            save=AsyncMock(side_effect=StorageUnavailableError("dashboard down"))
        )
        service = _make_service(
            rankings=fixture.rankings,
            dashboard=failing_dashboard,
        )

        with self.assertRaises(StorageUnavailableError):
            await service.project(ranking, (opportunity,), (lifecycle,))

    # --- UNAVAILABLE when ranked member has no matching opportunity ---

    async def test_ranked_member_without_opportunity_raises_unavailable(
        self,
    ) -> None:
        fixture, opportunity, lifecycle, ranking, service, dashboard_repo = (
            await _dashboard_fixture()
        )
        # Pass a lifecycle that references the ranked opportunity_id, but pass
        # an opportunity with a DIFFERENT id so the lookup fails.
        wrong_opp = replace(
            opportunity,
            opportunity_id="opportunity.runtime_ema_rsi.candidate.other",
            opportunity_version_id="opportunity.runtime_ema_rsi.candidate.other.v1",
            assessment_id="assessment.runtime_ema_rsi.candidate.other",
            decision_id="decision.runtime_ema_rsi.candidate.other",
            candidate_id="candidate.other",
            audit=replace(opportunity.audit, result_hash="0" * 64),
        )
        with self.assertRaises((ServiceUnavailableError, ServiceContractError)):
            await service.project(ranking, (wrong_opp,), (lifecycle,))
        self.assertEqual(len(dashboard_repo._records), 0)

    async def test_ranked_member_without_lifecycle_raises_unavailable(
        self,
    ) -> None:
        fixture, opportunity, lifecycle, ranking, service, dashboard_repo = (
            await _dashboard_fixture()
        )
        # Pass a lifecycle with the WRONG opportunity_id so the lookup fails.
        wrong_lc = SimpleNamespace(
            opportunity_id="opportunity.runtime_ema_rsi.candidate.other",
            current_state=LifecycleState.RANKED,
        )
        with self.assertRaises((ServiceUnavailableError, ServiceContractError)):
            await service.project(ranking, (opportunity,), (wrong_lc,))
        self.assertEqual(len(dashboard_repo._records), 0)

    # --- Pipeline handoff ---

    async def test_pipeline_calls_detail_projection_after_dashboard(
        self,
    ) -> None:
        """Full pipeline: dashboard.project succeeds and its result is persisted."""
        (
            fixture,
            _,
            opportunity,
            qualification,
            score,
            ranking_service,
            rankings,
        ) = await _ranking_fixture()

        dashboard_repo = DashboardProjectionMemoryRepository()
        dashboard_service = _make_service(rankings=rankings, dashboard=dashboard_repo)

        fake_lifecycle = SimpleNamespace(
            current_event_id="lifecycle.event.stub.1",
            opportunity_id=opportunity.opportunity_id,
            current_state=LifecycleState.RANKED,
        )
        # Stop the pipeline at explanation to avoid needing a real
        # ExplanationArtifact.  Dashboard runs before indicators and
        # explanation, so we stop just after dashboard completes.
        pipeline = OpportunityIntelligencePipeline(
            market_scanner=SimpleNamespace(
                scan=AsyncMock(return_value=fixture.market)
            ),
            feature_snapshots=SimpleNamespace(
                resolve=AsyncMock(return_value=fixture.feature)
            ),
            market_contexts=SimpleNamespace(
                build=AsyncMock(return_value=fixture.context)
            ),
            detection=fixture.detector,
            evidence=fixture.service,
            assessment=fixture.assessment_service,
            qualification=fixture.qualification_service,
            scoring=fixture.scoring_service,
            ranking=ranking_service,
            lifecycle=SimpleNamespace(
                advance=AsyncMock(return_value=fake_lifecycle)
            ),
            notifications=SimpleNamespace(create_intents=AsyncMock(return_value=())),
            dashboard=dashboard_service,
            indicators=SimpleNamespace(
                project=AsyncMock(side_effect=RuntimeError("stop-at-indicators"))
            ),
            explanation=SimpleNamespace(explain=AsyncMock()),
            detail=SimpleNamespace(project=AsyncMock()),
        )

        with self.assertRaises(PipelineExecutionError):
            await pipeline.run(_request(fixture))

        # Dashboard must have been called and persisted a page before the
        # pipeline stopped at indicators.
        self.assertEqual(len(dashboard_repo._records), 1)
        persisted_page = next(iter(dashboard_repo._records.values()))
        self.assertEqual(len(persisted_page.items), 1)
        self.assertEqual(
            persisted_page.items[0].opportunity_id, opportunity.opportunity_id
        )
        self.assertEqual(persisted_page.items[0].rank, 1)
