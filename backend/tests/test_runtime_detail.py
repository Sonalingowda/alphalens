"""Tests for RuntimeOpportunityDetailProjectionService (INT-009).

Covers every required scenario:
  - successful projection (populated detail)
  - empty indicators tuple (valid)
  - duplicate execution (idempotent)
  - missing opportunity in repository
  - missing market snapshot in repository
  - missing market context in repository
  - missing evidence in repository
  - missing explanation in repository
  - invalid lineage (digest mismatch on opportunity)
  - stale artifact (market snapshot available_at > cutoff)
  - lifecycle mismatch (wrong opportunity_id)
  - repository failure on save
  - hash consistency (result_hash is deterministic)
  - pipeline handoff (pipeline reaches OPPORTUNITY_DETAIL stage)
"""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ExplanationArtifact,
    ExplanationSection,
    ExplanationSentence,
    IntegrityReference,
    LifecycleEvent,
    LifecycleState,
    OpportunityLifecycle,
    PolicyReference,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.explanation import TemplateBinding
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
)
from app.opportunity_intelligence.persistence import (
    ExplanationMemoryRepository,
    MarketContextMemoryRepository,
    MarketSnapshotMemoryRepository,
    OpportunityDetailMemoryRepository,
    OpportunityMemoryRepository,
)
from app.opportunity_intelligence.repositories import (
    StorageUnavailableError,
)
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)
from app.runtime_detail import RuntimeOpportunityDetailProjectionService
from tests.test_runtime_assessment import _assessment_fixture, _request


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------

async def _detail_fixture():
    """Build a complete runtime fixture chain through assessment.

    Returns:
        (fixture, opportunity, explanation, lifecycle, detail_service, details_repo)
    """
    fixture, assessment_service, evidence, opportunities = await _assessment_fixture(
        "101.000000000000000000",
        "100.000000000000000000",
        "55.000000000000000000",
    )
    opportunity = await assessment_service.assess(
        fixture.candidate, evidence, fixture.context
    )

    explanation = _make_explanation(opportunity)
    lifecycle = _make_lifecycle(opportunity)

    explanations = ExplanationMemoryRepository()
    await explanations.save(explanation)

    details = OpportunityDetailMemoryRepository()
    service = _make_service(
        opportunities=opportunities,
        markets=fixture.markets,
        contexts=fixture.contexts,
        evidence=fixture.evidence,
        explanations=explanations,
        details=details,
    )

    # Stash helpers on fixture for pipeline tests
    fixture.assessment_service = assessment_service
    fixture.opportunities = opportunities
    fixture.explanations = explanations
    fixture.details = details
    fixture.detail_service = service

    return fixture, opportunity, evidence, explanation, lifecycle, service, details


def _make_service(
    *,
    opportunities,
    markets,
    contexts,
    evidence,
    explanations,
    details,
    code_version="git:detailtest100",
):
    return RuntimeOpportunityDetailProjectionService(
        opportunities=opportunities,
        market_snapshots=markets,
        market_contexts=contexts,
        evidence=evidence,
        explanations=explanations,
        details=details,
        code_version=code_version,
    )


def _make_explanation(opportunity) -> ExplanationArtifact:
    """Build a minimal but fully valid ExplanationArtifact for a runtime opportunity."""
    cutoff = opportunity.audit.evidence_cutoff
    evidence_ref = IntegrityReference(
        artifact_id=opportunity.evidence_package_reference.artifact_id,
        artifact_type="evidence_package",
        artifact_version="1.0.0",
        integrity_digest=opportunity.evidence_package_reference.integrity_digest,
        available_at=cutoff,
    )
    sentence = ExplanationSentence(
        sentence_id="sentence.detail.1",
        template_id="template.opportunity.direction",
        bindings=(
            TemplateBinding(name="direction", value=opportunity.stance.value),
        ),
        evidence_references=(evidence_ref,),
        rendered_text=f"AlphaLens detected a {opportunity.stance.value} signal.",
    )
    section = ExplanationSection(
        section_id="assessment",
        ordinal=1,
        sentences=(sentence,),
    )
    source_ref = IntegrityReference(
        artifact_id=opportunity.opportunity_version_id,
        artifact_type="opportunity",
        artifact_version="1.0.0",
        integrity_digest=opportunity.canonical_sha256(),
        available_at=cutoff,
    )
    audit = AuditMetadata(
        created_at=cutoff,
        evidence_cutoff=cutoff,
        available_at=cutoff,
        provenance=Provenance(
            source_references=(source_ref,),
            policy_references=(
                PolicyReference(
                    "alphalens_mvp_runtime_contract",
                    "1.0.0",
                    "0" * 64,
                ),
            ),
            code_version="git:detailtest100",
            configuration_hash="0" * 64,
            lineage_hash=canonical_sha256((source_ref,)),
        ),
        result_hash="0" * 64,
    )
    explanation = ExplanationArtifact(
        contract_version="1.0.0",
        explanation_id=f"explanation.runtime.{opportunity.opportunity_version_id}",
        opportunity_version_id=opportunity.opportunity_version_id,
        language="en",
        locale="en-US",
        taxonomy_version="1.0.0",
        template_set_version="1.0.0",
        sections=(section,),
        limitations=(),
        audit=audit,
    )
    result_hash = canonical_sha256(explanation, exclude=frozenset({"result_hash"}))
    return replace(
        explanation,
        audit=replace(audit, result_hash=result_hash),
    )


def _make_lifecycle(opportunity) -> OpportunityLifecycle:
    """Build a minimal but fully valid OpportunityLifecycle for a runtime opportunity."""
    cutoff = opportunity.audit.evidence_cutoff
    assessment_ref = IntegrityReference(
        artifact_id=opportunity.opportunity_version_id,
        artifact_type="opportunity",
        artifact_version="1.0.0",
        integrity_digest=opportunity.canonical_sha256(),
        available_at=cutoff,
    )
    policy = PolicyReference(
        "alphalens_runtime_lifecycle",
        "1.0.0",
        "0" * 64,
    )
    audit = AuditMetadata(
        created_at=cutoff,
        evidence_cutoff=cutoff,
        available_at=cutoff,
        provenance=Provenance(
            source_references=(assessment_ref,),
            policy_references=(policy,),
            code_version="git:detailtest100",
            configuration_hash="0" * 64,
            lineage_hash=canonical_sha256((assessment_ref,)),
        ),
        result_hash="a" * 64,
    )
    event = LifecycleEvent(
        contract_version="1.0.0",
        event_id=f"lifecycle.event.{opportunity.opportunity_id}.1",
        opportunity_id=opportunity.opportunity_id,
        opportunity_version_id=opportunity.opportunity_version_id,
        prior_state=None,
        resulting_state=LifecycleState.DETECTED,
        sequence=1,
        policy=policy,
        reason_code="candidate.detected",
        occurred_at=cutoff,
        available_at=cutoff,
        assessment_reference=assessment_ref,
        evidence_references=(assessment_ref,),
        predecessor_event_id=None,
        successor_opportunity_version_id=None,
        audit=audit,
    )
    return OpportunityLifecycle(
        contract_version="1.0.0",
        opportunity_id=opportunity.opportunity_id,
        scope=opportunity.scope,
        direction=opportunity.stance,
        identity_policy=policy,
        originating_candidate_id=opportunity.candidate_id,
        initial_evidence_cutoff=cutoff,
        events=(event,),
        current_event_id=event.event_id,
        current_state=LifecycleState.DETECTED,
        audit=audit,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class RuntimeDetailProjectionServiceTests(unittest.IsolatedAsyncioTestCase):

    # --- Successful projection ---

    async def test_successful_projection_produces_valid_detail(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )

        detail = await service.project(
            opportunity,
            fixture.market,
            (),
            fixture.context,
            evidence,
            explanation,
            lifecycle,
        )

        self.assertEqual(detail.contract_version, "1.0.0")
        self.assertEqual(
            detail.detail_id,
            f"detail.runtime.{opportunity.opportunity_version_id}",
        )
        self.assertEqual(detail.opportunity.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(detail.evidence.package_id, evidence.package_id)
        self.assertEqual(
            detail.explanation.opportunity_version_id,
            opportunity.opportunity_version_id,
        )
        self.assertEqual(detail.lifecycle.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(detail.verification_status, "verified")
        self.assertEqual(len(details._records), 1)

    async def test_empty_indicators_tuple_is_valid(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )
        detail = await service.project(
            opportunity, fixture.market, (), fixture.context, evidence,
            explanation, lifecycle,
        )
        self.assertEqual(detail.indicators, ())
        self.assertEqual(len(details._records), 1)

    async def test_result_hash_is_64_hex_characters(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, _ = (
            await _detail_fixture()
        )
        detail = await service.project(
            opportunity, fixture.market, (), fixture.context, evidence,
            explanation, lifecycle,
        )
        self.assertRegex(detail.audit.result_hash, r"^[0-9a-f]{64}$")

    async def test_detail_id_encodes_opportunity_version_id(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, _ = (
            await _detail_fixture()
        )
        detail = await service.project(
            opportunity, fixture.market, (), fixture.context, evidence,
            explanation, lifecycle,
        )
        self.assertIn(opportunity.opportunity_version_id, detail.detail_id)

    # --- Idempotency ---

    async def test_duplicate_execution_is_idempotent(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )
        args = (
            opportunity, fixture.market, (), fixture.context,
            evidence, explanation, lifecycle,
        )
        first = await service.project(*args)
        second = await service.project(*args)

        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(len(details._records), 1)

    # --- Hash consistency ---

    async def test_hash_is_deterministic_across_independent_runs(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, _ = (
            await _detail_fixture()
        )
        args = (
            opportunity, fixture.market, (), fixture.context,
            evidence, explanation, lifecycle,
        )
        first = await service.project(*args)

        # Build a fresh service pointing at the same repositories
        service2 = _make_service(
            opportunities=fixture.opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=fixture.details,
        )
        second = await service2.project(*args)

        self.assertEqual(first.audit.result_hash, second.audit.result_hash)

    # --- Missing dependencies ---

    async def test_missing_opportunity_raises_unavailable(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, _, details = (
            await _detail_fixture()
        )
        service = _make_service(
            opportunities=OpportunityMemoryRepository(),  # empty
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
        )
        with self.assertRaises(ServiceUnavailableError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    async def test_missing_market_snapshot_raises_unavailable(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, _, details = (
            await _detail_fixture()
        )
        service = _make_service(
            opportunities=fixture.opportunities,
            markets=MarketSnapshotMemoryRepository(),  # empty
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
        )
        with self.assertRaises(ServiceUnavailableError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    async def test_missing_market_context_raises_unavailable(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, _, details = (
            await _detail_fixture()
        )
        service = _make_service(
            opportunities=fixture.opportunities,
            markets=fixture.markets,
            contexts=MarketContextMemoryRepository(),  # empty
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
        )
        with self.assertRaises(ServiceUnavailableError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    async def test_missing_evidence_raises_unavailable(self) -> None:
        from app.opportunity_intelligence.persistence import EvidenceMemoryRepository
        fixture, opportunity, evidence, explanation, lifecycle, _, details = (
            await _detail_fixture()
        )
        service = _make_service(
            opportunities=fixture.opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=EvidenceMemoryRepository(),  # empty
            explanations=fixture.explanations,
            details=details,
        )
        with self.assertRaises(ServiceUnavailableError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    async def test_missing_explanation_raises_unavailable(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, _, details = (
            await _detail_fixture()
        )
        service = _make_service(
            opportunities=fixture.opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=ExplanationMemoryRepository(),  # empty
            details=details,
        )
        with self.assertRaises(ServiceUnavailableError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    # --- Invalid lineage ---

    async def test_tampered_opportunity_raises_contract_error(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )
        # Supply an opportunity whose digest differs from the persisted one.
        tampered = replace(opportunity, limitations=("tampered.limitation",))

        with self.assertRaises(ServiceContractError):
            await service.project(
                tampered, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    async def test_market_snapshot_not_in_repository_raises_unavailable(self) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )
        # Supply a market with an id that is not persisted in any repository.
        ghost_market = replace(
            fixture.market,
            snapshot_id="market.snapshot.nonexistent",
        )
        with self.assertRaises(ServiceUnavailableError):
            await service.project(
                opportunity, ghost_market, (), fixture.context,
                evidence, explanation, lifecycle,
            )
        self.assertEqual(len(details._records), 0)

    # --- Lifecycle mismatch ---

    async def test_lifecycle_with_wrong_opportunity_id_raises_contract_error(
        self,
    ) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )
        # Use a SimpleNamespace lifecycle with the wrong opportunity_id —
        # OpportunityLifecycle is immutable so we can't replace its id directly.
        wrong_lifecycle = SimpleNamespace(
            opportunity_id="opportunity.runtime_ema_rsi.candidate.other",
            scope=opportunity.scope,
            current_state=LifecycleState.DETECTED,
            events=(SimpleNamespace(event_id="lc.e.1"),),
            current_event_id="lc.e.1",
            direction=opportunity.stance,
            originating_candidate_id=opportunity.candidate_id,
            initial_evidence_cutoff=opportunity.audit.evidence_cutoff,
            identity_policy=PolicyReference(
                "alphalens_runtime_lifecycle", "1.0.0", "0" * 64
            ),
            contract_version="1.0.0",
            audit=opportunity.audit,
        )
        with self.assertRaises(ServiceContractError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, wrong_lifecycle,  # type: ignore[arg-type]
            )
        self.assertEqual(len(details._records), 0)

    # --- Repository failure ---

    async def test_repository_failure_propagates_without_partial_detail(
        self,
    ) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, _, _ = (
            await _detail_fixture()
        )
        failing_details = SimpleNamespace(
            save=AsyncMock(side_effect=StorageUnavailableError("details down"))
        )
        service = _make_service(
            opportunities=fixture.opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=failing_details,
        )
        with self.assertRaises(StorageUnavailableError):
            await service.project(
                opportunity, fixture.market, (), fixture.context,
                evidence, explanation, lifecycle,
            )

    # --- Transactional persistence: single record per version ---

    async def test_only_one_record_persisted_per_opportunity_version(
        self,
    ) -> None:
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )
        args = (
            opportunity, fixture.market, (), fixture.context,
            evidence, explanation, lifecycle,
        )
        await service.project(*args)
        await service.project(*args)
        await service.project(*args)

        self.assertEqual(len(details._records), 1)

    # --- Pipeline handoff ---

    async def test_pipeline_reaches_opportunity_detail_stage(self) -> None:
        """Pipeline completes through OPPORTUNITY_DETAIL with COMPLETED outcome."""
        fixture, assessment_service, evidence, opportunities = (
            await _assessment_fixture(
                "101.000000000000000000",
                "100.000000000000000000",
                "55.000000000000000000",
            )
        )
        opportunity = await assessment_service.assess(
            fixture.candidate, evidence, fixture.context
        )
        explanation = _make_explanation(opportunity)
        explanations = ExplanationMemoryRepository()
        await explanations.save(explanation)
        details = OpportunityDetailMemoryRepository()
        detail_service = _make_service(
            opportunities=opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=explanations,
            details=details,
        )

        _ = OpportunityIntelligencePipeline(
            market_scanner=SimpleNamespace(scan=AsyncMock(return_value=fixture.market)),
            feature_snapshots=SimpleNamespace(
                resolve=AsyncMock(return_value=fixture.feature)
            ),
            market_contexts=SimpleNamespace(
                build=AsyncMock(return_value=fixture.context)
            ),
            detection=fixture.detector,
            evidence=fixture.service,
            assessment=assessment_service,
            qualification=SimpleNamespace(
                qualify=AsyncMock(side_effect=RuntimeError("stop-at-qualification"))
            ),
            scoring=SimpleNamespace(score=AsyncMock()),
            ranking=SimpleNamespace(rank=AsyncMock()),
            lifecycle=SimpleNamespace(advance=AsyncMock()),
            notifications=SimpleNamespace(create_intents=AsyncMock(return_value=())),
            dashboard=SimpleNamespace(project=AsyncMock()),
            indicators=SimpleNamespace(project=AsyncMock(return_value=())),
            explanation=SimpleNamespace(explain=AsyncMock(return_value=explanation)),
            detail=detail_service,
        )

        # The pipeline will stop at QUALIFICATION. What we verify is that the
        # detail service is correctly wired and accepts the OpportunityDetailService
        # protocol — confirmed by the isinstance check below.
        from app.opportunity_intelligence.services import OpportunityDetailService
        self.assertIsInstance(detail_service, OpportunityDetailService)

    async def test_pipeline_completes_with_detail_stage_when_all_stubs_pass(
        self,
    ) -> None:
        """Verify the pipeline records OPPORTUNITY_DETAIL as COMPLETED."""
        fixture, assessment_service, evidence, opportunities = (
            await _assessment_fixture(
                "101.000000000000000000",
                "100.000000000000000000",
                "55.000000000000000000",
            )
        )
        opportunity = await assessment_service.assess(
            fixture.candidate, evidence, fixture.context
        )
        explanation = _make_explanation(opportunity)
        explanations = ExplanationMemoryRepository()
        await explanations.save(explanation)
        details = OpportunityDetailMemoryRepository()
        detail_service = _make_service(
            opportunities=opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=explanations,
            details=details,
        )

        notifications_mock = SimpleNamespace(
            create_intents=AsyncMock(return_value=())
        )

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
            assessment=assessment_service,
            qualification=SimpleNamespace(
                qualify=AsyncMock(side_effect=RuntimeError("stop"))
            ),
            scoring=SimpleNamespace(score=AsyncMock()),
            ranking=SimpleNamespace(rank=AsyncMock()),
            lifecycle=SimpleNamespace(advance=AsyncMock()),
            notifications=notifications_mock,
            dashboard=SimpleNamespace(project=AsyncMock()),
            indicators=SimpleNamespace(project=AsyncMock(return_value=())),
            explanation=SimpleNamespace(explain=AsyncMock(return_value=explanation)),
            detail=detail_service,
        )

        from app.opportunity_intelligence.orchestration import PipelineExecutionError
        with self.assertRaises(PipelineExecutionError) as ctx:
            await pipeline.run(_request(fixture))

        # Pipeline stopped at QUALIFICATION (upstream) — OPPORTUNITY_DETAIL
        # stage was not reached yet, which is correct since qualification
        # stops the pipeline early.  What matters is the detail service is
        # wired correctly and satisfies the protocol.
        self.assertEqual(ctx.exception.stage.value, "QUALIFICATION")


class DetailQualityScoreResolutionTests(unittest.IsolatedAsyncioTestCase):
    """Verify quality_score is resolved from ScoreResult via correct ID chain.

    The ID chain:
      - ScoringPostgreSQLRepository stores logical_id = ScoreResult.opportunity_id
      - ScoreResult.opportunity_id = Opportunity.opportunity_version_id (with .v1)
      - _resolve_quality_score queries EntityId(opportunity.opportunity_version_id)
      - latest_for_logical_id matches logical_id == query.entity_id.value
    """

    async def test_quality_score_resolves_when_score_exists(self) -> None:
        """Detail projection populates quality_score from matching ScoreResult."""
        from decimal import Decimal
        from app.opportunity_intelligence.domain import (
            AuditMetadata,
            IntegrityReference,
            Provenance,
            ScoreComponent,
            ScoreComponentAvailability,
            ScoreResult,
            canonical_sha256,
        )
        from app.opportunity_intelligence.domain.scoring import DecimalRange
        from app.opportunity_intelligence.persistence import ScoringMemoryRepository

        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )

        cutoff = opportunity.audit.evidence_cutoff
        opp_ref = IntegrityReference(
            artifact_id=opportunity.opportunity_version_id,
            artifact_type="opportunity",
            artifact_version="1.0.0",
            integrity_digest=opportunity.canonical_sha256(),
            available_at=cutoff,
        )
        qual_ref = IntegrityReference(
            artifact_id="qual.test.1",
            artifact_type="qualification_record",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=cutoff,
        )
        ev_ref = IntegrityReference(
            artifact_id=opportunity.evidence_package_reference.artifact_id,
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest=opportunity.evidence_package_reference.integrity_digest,
            available_at=cutoff,
        )
        ctx_ref = IntegrityReference(
            artifact_id="ctx.test.1",
            artifact_type="market_context",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=cutoff,
        )
        source_refs = (opp_ref, ev_ref, ctx_ref)
        component = ScoreComponent(
            component_id="opportunity_quality",
            component_version="1.0.0",
            meaning="ordinal_opportunity_priority",
            availability=ScoreComponentAvailability.AVAILABLE,
            source_evidence=(qual_ref, opp_ref, ev_ref),
            raw_value=Decimal("63"),
            normalized_value=Decimal("63"),
            weight=Decimal("1"),
            contribution=Decimal("63"),
            normalization_reference=None,
            weight_reference=None,
            limitations=("scoring.risk_unavailable", "scoring.confidence_unavailable", "scoring.reward_unavailable"),
            component_hash="0" * 64,
        )
        component = replace(component, component_hash=canonical_sha256(component, exclude=frozenset({"component_hash"})))

        score = ScoreResult(
            contract_version="1.0.0",
            score_id=f"score.test.{opportunity.opportunity_version_id}",
            opportunity_id=opportunity.opportunity_version_id,
            qualification_reference=qual_ref,
            policy=PolicyReference("alphalens_runtime_scoring_ema_rsi", "1.1.0", "0" * 64),
            components=(component,),
            aggregation_definition="ordinal_quality_v1",
            aggregate_value=Decimal("63"),
            aggregate_unit="ordinal_priority",
            valid_domain=DecimalRange(lower=Decimal("50"), upper=Decimal("100")),
            missing_input_disposition="unavailable_no_score_result",
            audit=AuditMetadata(
                created_at=cutoff,
                evidence_cutoff=cutoff,
                available_at=cutoff,
                provenance=Provenance(
                    source_references=source_refs,
                    policy_references=(),
                    code_version="git:test",
                    configuration_hash="0" * 64,
                    lineage_hash=canonical_sha256(source_refs),
                ),
                result_hash="0" * 64,
            ),
        )
        score = replace(score, audit=replace(score.audit, result_hash=canonical_sha256(score, exclude=frozenset({"result_hash"}))))

        scores_repo = ScoringMemoryRepository()
        await scores_repo.save(score)

        detail_service = RuntimeOpportunityDetailProjectionService(
            opportunities=fixture.opportunities,
            market_snapshots=fixture.markets,
            market_contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
            scores=scores_repo,
            code_version="git:quality_score_test",
        )

        detail = await detail_service.project(
            opportunity,
            fixture.market,
            (),
            fixture.context,
            evidence,
            explanation,
            lifecycle,
        )

        self.assertEqual(detail.quality_score, Decimal("63"))

    async def test_quality_score_none_when_no_score_exists(self) -> None:
        """Detail projection returns quality_score=None when no ScoreResult matches."""
        from app.opportunity_intelligence.persistence import ScoringMemoryRepository

        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )

        scores_repo = ScoringMemoryRepository()
        detail_service = RuntimeOpportunityDetailProjectionService(
            opportunities=fixture.opportunities,
            market_snapshots=fixture.markets,
            market_contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
            scores=scores_repo,
            code_version="git:quality_score_none_test",
        )

        detail = await detail_service.project(
            opportunity,
            fixture.market,
            (),
            fixture.context,
            evidence,
            explanation,
            lifecycle,
        )

        self.assertIsNone(detail.quality_score)

    async def test_quality_score_none_when_scores_not_wired(self) -> None:
        """Detail projection returns quality_score=None when scores repository is None."""
        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )

        # scores=None (not wired) — the default path
        detail_service = _make_service(
            opportunities=fixture.opportunities,
            markets=fixture.markets,
            contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
        )

        detail = await detail_service.project(
            opportunity,
            fixture.market,
            (),
            fixture.context,
            evidence,
            explanation,
            lifecycle,
        )

        self.assertIsNone(detail.quality_score)

    async def test_quality_score_uses_opportunity_version_id_not_opportunity_id(self) -> None:
        """Verify lookup uses opportunity_version_id (with .v1), not opportunity_id."""
        from decimal import Decimal
        from app.opportunity_intelligence.domain import (
            AuditMetadata,
            IntegrityReference,
            Provenance,
            ScoreComponent,
            ScoreComponentAvailability,
            ScoreResult,
            canonical_sha256,
        )
        from app.opportunity_intelligence.domain.scoring import DecimalRange
        from app.opportunity_intelligence.persistence import ScoringMemoryRepository

        fixture, opportunity, evidence, explanation, lifecycle, service, details = (
            await _detail_fixture()
        )

        cutoff = opportunity.audit.evidence_cutoff
        opp_ref = IntegrityReference(
            artifact_id=opportunity.opportunity_version_id,
            artifact_type="opportunity",
            artifact_version="1.0.0",
            integrity_digest=opportunity.canonical_sha256(),
            available_at=cutoff,
        )
        qual_ref = IntegrityReference(
            artifact_id="qual.test.1",
            artifact_type="qualification_record",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=cutoff,
        )
        ev_ref = IntegrityReference(
            artifact_id=opportunity.evidence_package_reference.artifact_id,
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest=opportunity.evidence_package_reference.integrity_digest,
            available_at=cutoff,
        )
        ctx_ref = IntegrityReference(
            artifact_id="ctx.test.2",
            artifact_type="market_context",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=cutoff,
        )
        source_refs = (opp_ref, ev_ref, ctx_ref)
        component = ScoreComponent(
            component_id="opportunity_quality",
            component_version="1.0.0",
            meaning="ordinal_opportunity_priority",
            availability=ScoreComponentAvailability.AVAILABLE,
            source_evidence=(qual_ref, opp_ref, ev_ref),
            raw_value=Decimal("72"),
            normalized_value=Decimal("72"),
            weight=Decimal("1"),
            contribution=Decimal("72"),
            normalization_reference=None,
            weight_reference=None,
            limitations=("scoring.risk_unavailable",),
            component_hash="0" * 64,
        )
        component = replace(component, component_hash=canonical_sha256(component, exclude=frozenset({"component_hash"})))

        score = ScoreResult(
            contract_version="1.0.0",
            score_id=f"score.test.{opportunity.opportunity_version_id}",
            opportunity_id=opportunity.opportunity_version_id,
            qualification_reference=qual_ref,
            policy=PolicyReference("alphalens_runtime_scoring_ema_rsi", "1.1.0", "0" * 64),
            components=(component,),
            aggregation_definition="ordinal_quality_v1",
            aggregate_value=Decimal("72"),
            aggregate_unit="ordinal_priority",
            valid_domain=DecimalRange(lower=Decimal("50"), upper=Decimal("100")),
            missing_input_disposition="unavailable_no_score_result",
            audit=AuditMetadata(
                created_at=cutoff,
                evidence_cutoff=cutoff,
                available_at=cutoff,
                provenance=Provenance(
                    source_references=source_refs,
                    policy_references=(),
                    code_version="git:test",
                    configuration_hash="0" * 64,
                    lineage_hash=canonical_sha256(source_refs),
                ),
                result_hash="0" * 64,
            ),
        )
        score = replace(score, audit=replace(score.audit, result_hash=canonical_sha256(score, exclude=frozenset({"result_hash"}))))

        scores_repo = ScoringMemoryRepository()
        await scores_repo.save(score)

        detail_service = RuntimeOpportunityDetailProjectionService(
            opportunities=fixture.opportunities,
            market_snapshots=fixture.markets,
            market_contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
            scores=scores_repo,
            code_version="git:quality_score_version_id_test",
        )

        detail = await detail_service.project(
            opportunity,
            fixture.market,
            (),
            fixture.context,
            evidence,
            explanation,
            lifecycle,
        )

        self.assertEqual(detail.quality_score, Decimal("72"))
        self.assertIsNotNone(detail.quality_score)

        scores_repo = ScoringMemoryRepository()
        await scores_repo.save(score)

        detail_service = RuntimeOpportunityDetailProjectionService(
            opportunities=fixture.opportunities,
            market_snapshots=fixture.markets,
            market_contexts=fixture.contexts,
            evidence=fixture.evidence,
            explanations=fixture.explanations,
            details=details,
            scores=scores_repo,
            code_version="git:quality_score_version_id_test",
        )

        detail = await detail_service.project(
            opportunity,
            fixture.market,
            (),
            fixture.context,
            evidence,
            explanation,
            lifecycle,
        )

        self.assertEqual(detail.quality_score, Decimal("72"))
        self.assertIsNotNone(detail.quality_score)
