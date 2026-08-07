"""Production factory for the complete OpportunityIntelligencePipeline.

This module constructs the fully-wired runtime pipeline from PostgreSQL
repositories and the concrete runtime service implementations. It is the
single composition root for the write path of the MVP runtime system.

Only this module and prediction_api.py may import from runtime_* service
packages. No other production module should depend on this file.
"""

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.opportunity_intelligence.domain import MarketScope, MarketSnapshot
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineExecutionError,
    PipelineOutcome,
    PipelineRunRequest,
    PipelineRunResult,
)
from app.opportunity_intelligence.persistence import (
    DashboardProjectionPostgreSQLRepository,
    DetectionPostgreSQLRepository,
    EvidencePostgreSQLRepository,
    ExplanationPostgreSQLRepository,
    FeatureSnapshotPostgreSQLRepository,
    MarketContextPostgreSQLRepository,
    MarketSnapshotPostgreSQLRepository,
    NotificationPostgreSQLRepository,
    OpportunityDetailPostgreSQLRepository,
    OpportunityPostgreSQLRepository,
    QualificationPostgreSQLRepository,
    RankingPostgreSQLRepository,
    ScoringPostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.runtime_assessment import RuntimeAssessmentService
from app.runtime_context import RuntimeMarketContextService
from app.runtime_dashboard import RuntimeDashboardProjectionService
from app.runtime_detail import RuntimeOpportunityDetailProjectionService
from app.runtime_detection import RuntimeOpportunityDetectionService
from app.runtime_evidence import RuntimeEvidenceService
from app.runtime_features import RuntimeFeatureEngine
from app.runtime_notification import RuntimeNotificationService
from app.runtime_qualification import RuntimeQualificationService
from app.runtime_ranking import RuntimeRankingService
from app.runtime_scoring import RuntimeScoringService


logger = logging.getLogger("alphalens.runtime_pipeline")

_CODE_VERSION = "alphalens.runtime.1.0.0"

# Only the 5m timeframe feeds the runtime intelligence pipeline.
_PIPELINE_SCOPE = MarketScope(instrument="BTCUSDT", timeframe="5m")


def build_runtime_pipeline(
    session_factory: async_sessionmaker[AsyncSession],
) -> "RuntimeIntelligencePipeline":
    """Construct the fully-wired runtime intelligence pipeline.

    All repositories are PostgreSQL-backed.  This factory is called once at
    application startup and the returned object is held for the lifetime of
    the process.
    """
    market_snapshots = MarketSnapshotPostgreSQLRepository(session_factory)
    feature_snapshots = FeatureSnapshotPostgreSQLRepository(session_factory)
    market_contexts = MarketContextPostgreSQLRepository(session_factory)
    detections = DetectionPostgreSQLRepository(session_factory)
    evidence_repo = EvidencePostgreSQLRepository(session_factory)
    opportunities = OpportunityPostgreSQLRepository(session_factory)
    qualifications = QualificationPostgreSQLRepository(session_factory)
    scores = ScoringPostgreSQLRepository(session_factory)
    rankings = RankingPostgreSQLRepository(session_factory)
    dashboard_repo = DashboardProjectionPostgreSQLRepository(session_factory)
    detail_repo = OpportunityDetailPostgreSQLRepository(session_factory)
    explanations = ExplanationPostgreSQLRepository(session_factory)
    notifications = NotificationPostgreSQLRepository(session_factory)
    # LifecyclePostgreSQLRepository is reserved for a full lifecycle service.

    feature_engine = RuntimeFeatureEngine(
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        code_version=_CODE_VERSION,
    )
    context_service = RuntimeMarketContextService(
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        code_version=_CODE_VERSION,
    )
    detection_service = RuntimeOpportunityDetectionService(
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        detections=detections,
        code_version=_CODE_VERSION,
    )
    evidence_service = RuntimeEvidenceService(
        candidates=detections,
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        evidence=evidence_repo,
        code_version=_CODE_VERSION,
    )
    assessment_service = RuntimeAssessmentService(
        candidates=detections,
        evidence=evidence_repo,
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        opportunities=opportunities,
        code_version=_CODE_VERSION,
    )
    qualification_service = RuntimeQualificationService(
        opportunities=opportunities,
        evidence=evidence_repo,
        market_contexts=market_contexts,
        feature_snapshots=feature_snapshots,
        market_snapshots=market_snapshots,
        qualifications=qualifications,
        code_version=_CODE_VERSION,
    )
    scoring_service = RuntimeScoringService(
        opportunities=opportunities,
        qualifications=qualifications,
        evidence=evidence_repo,
        market_contexts=market_contexts,
        scores=scores,
        code_version=_CODE_VERSION,
    )
    ranking_service = RuntimeRankingService(
        scores=scores,
        qualifications=qualifications,
        opportunities=opportunities,
        rankings=rankings,
        code_version=_CODE_VERSION,
    )
    notification_service = RuntimeNotificationService(
        rankings=rankings,
        opportunities=opportunities,
        notifications=notifications,
        code_version=_CODE_VERSION,
    )
    dashboard_service = RuntimeDashboardProjectionService(
        rankings=rankings,
        dashboard=dashboard_repo,
        code_version=_CODE_VERSION,
    )
    detail_service = RuntimeOpportunityDetailProjectionService(
        opportunities=opportunities,
        market_snapshots=market_snapshots,
        market_contexts=market_contexts,
        evidence=evidence_repo,
        explanations=explanations,
        details=detail_repo,
        code_version=_CODE_VERSION,
    )

    pipeline = OpportunityIntelligencePipeline(
        market_scanner=_MarketScannerAdapter(market_snapshots),
        feature_snapshots=feature_engine,
        market_contexts=context_service,
        detection=detection_service,
        evidence=evidence_service,
        assessment=assessment_service,
        qualification=qualification_service,
        scoring=scoring_service,
        ranking=ranking_service,
        lifecycle=_StubLifecycleService(),
        notifications=notification_service,
        dashboard=dashboard_service,
        indicators=_StubIndicatorService(),
        explanation=_StubExplanationService(),
        detail=detail_service,
    )

    return RuntimeIntelligencePipeline(
        pipeline=pipeline,
        scope=_PIPELINE_SCOPE,
    )


class RuntimeIntelligencePipeline:
    """Stateful wrapper that runs the pipeline for a given market scope."""

    def __init__(
        self,
        pipeline: OpportunityIntelligencePipeline,
        scope: MarketScope,
    ) -> None:
        self._pipeline = pipeline
        self._scope = scope

    async def run_for_snapshot(
        self,
        snapshot: MarketSnapshot,
        as_of: object,
    ) -> PipelineRunResult | None:
        """Run one pipeline cycle for a newly persisted market snapshot.

        Returns None (not an error) for non-5m snapshots.  Logs and returns
        None on expected terminal outcomes (NO_CANDIDATE, NOT_QUALIFIED).
        Repository and pipeline errors are logged and not re-raised so that
        a single cycle failure does not crash the ingestion loop.
        """
        if snapshot.scope != self._scope:
            return None

        import datetime as dt
        cutoff = snapshot.audit.available_at
        if not isinstance(cutoff, dt.datetime):
            logger.error(
                "runtime_pipeline_invalid_cutoff snapshot_id=%s",
                snapshot.snapshot_id,
            )
            return None

        run_id = f"pipeline.run.{snapshot.snapshot_id}.{uuid4().hex[:8]}"
        request = PipelineRunRequest(
            run_id=run_id,
            query=ScopedRepositoryQuery(
                scope=self._scope,
                as_of=cutoff,
                limit=1,
            ),
        )

        logger.info(
            "runtime_pipeline_start run_id=%s snapshot_id=%s",
            run_id,
            snapshot.snapshot_id,
        )

        try:
            result = await self._pipeline.run(request)
        except PipelineExecutionError as error:
            logger.error(
                "runtime_pipeline_execution_error run_id=%s stage=%s trace=%s",
                error.run_id,
                error.stage.value,
                error.trace_hash,
            )
            for stage_record in error.stages:
                logger.error(
                    "runtime_pipeline_stage run_id=%s stage=%s status=%s reason=%s artifacts=%s",
                    run_id,
                    stage_record.stage.value,
                    stage_record.status.value,
                    stage_record.reason_code,
                    stage_record.artifact_ids,
                )
            return None
        except Exception:
            logger.exception(
                "runtime_pipeline_unexpected_error run_id=%s",
                run_id,
            )
            return None

        for stage_record in result.stages:
            logger.info(
                "runtime_pipeline_stage run_id=%s stage=%s status=%s reason=%s",
                run_id,
                stage_record.stage.value,
                stage_record.status.value,
                stage_record.reason_code,
            )

        logger.info(
            "runtime_pipeline_complete run_id=%s outcome=%s stages=%d",
            run_id,
            result.outcome.value,
            len(result.stages),
        )

        if result.outcome not in {
            PipelineOutcome.COMPLETED,
            PipelineOutcome.NO_CANDIDATE,
            PipelineOutcome.NOT_QUALIFIED,
        }:
            logger.warning(
                "runtime_pipeline_blocked run_id=%s outcome=%s",
                run_id,
                result.outcome.value,
            )

        return result


# ---------------------------------------------------------------------------
# Minimal stub services for pipeline stages not yet fully implemented.
# These stubs satisfy the pipeline contracts and produce no side effects.
# ---------------------------------------------------------------------------

class _MarketScannerAdapter:
    """Adapt MarketSnapshotRepository to the MarketScannerService protocol."""

    def __init__(self, repository: MarketSnapshotPostgreSQLRepository) -> None:
        self._repository = repository

    async def scan(self, query: ScopedRepositoryQuery) -> MarketSnapshot:
        return await self._repository.get_latest(query)


class _StubLifecycleService:
    """Minimal lifecycle stub — advances to DETECTED without persistence.

    A full RuntimeLifecycleService is not implemented yet.  This stub
    returns a simple in-memory lifecycle so the pipeline can continue to
    Dashboard and Detail Projection.
    """

    async def advance(
        self,
        opportunity,
        qualification,
        ranking,
        previous,
    ):
        from app.opportunity_intelligence.domain import (
            AuditMetadata,
            LifecycleEvent,
            LifecycleState,
            OpportunityLifecycle,
            PolicyReference,
            Provenance,
            canonical_sha256,
        )
        from app.opportunity_intelligence.domain import IntegrityReference

        cutoff = opportunity.audit.evidence_cutoff
        policy = PolicyReference(
            "alphalens_runtime_lifecycle_stub",
            "1.0.0",
            "0" * 64,
        )
        assessment_ref = IntegrityReference(
            artifact_id=opportunity.opportunity_version_id,
            artifact_type="opportunity",
            artifact_version="1.0.0",
            integrity_digest=opportunity.canonical_sha256(),
            available_at=cutoff,
        )
        source_refs = (assessment_ref,)
        audit = AuditMetadata(
            created_at=cutoff,
            evidence_cutoff=cutoff,
            available_at=cutoff,
            provenance=Provenance(
                source_references=source_refs,
                policy_references=(policy,),
                code_version=_CODE_VERSION,
                configuration_hash="0" * 64,
                lineage_hash=canonical_sha256(source_refs),
            ),
            result_hash="0" * 64,
        )
        event_id = (
            f"lifecycle.event.{opportunity.opportunity_id}.1"
        )
        event = LifecycleEvent(
            contract_version="1.0.0",
            event_id=event_id,
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
        from dataclasses import replace
        from app.opportunity_intelligence.domain import canonical_sha256 as cs
        result_hash = cs(event, exclude=frozenset({"result_hash"}))
        event = replace(event, audit=replace(audit, result_hash=result_hash))

        lifecycle_audit = replace(
            audit,
            result_hash=cs(
                OpportunityLifecycle(
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
                ),
                exclude=frozenset({"result_hash"}),
            ),
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
            audit=lifecycle_audit,
        )


class _StubIndicatorService:
    """Returns empty indicators — RuntimeIndicatorService not yet implemented."""

    async def project(self, feature_snapshot) -> tuple:
        return ()


class _StubExplanationService:
    """Returns a minimal deterministic explanation — full service not yet implemented."""

    async def explain(
        self,
        opportunity,
        evidence,
        market_context,
        lifecycle,
    ):
        from dataclasses import replace as dr
        from app.opportunity_intelligence.domain import (
            AuditMetadata,
            ExplanationArtifact,
            ExplanationSection,
            ExplanationSentence,
            IntegrityReference,
            PolicyReference,
            Provenance,
            canonical_sha256,
        )
        from app.opportunity_intelligence.domain.explanation import TemplateBinding

        cutoff = opportunity.audit.evidence_cutoff
        policy = PolicyReference(
            "alphalens_runtime_explanation_stub",
            "1.0.0",
            "0" * 64,
        )
        evidence_ref = IntegrityReference(
            artifact_id=opportunity.evidence_package_reference.artifact_id,
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest=opportunity.evidence_package_reference.integrity_digest,
            available_at=cutoff,
        )
        source_refs = (
            IntegrityReference(
                artifact_id=opportunity.opportunity_version_id,
                artifact_type="opportunity",
                artifact_version="1.0.0",
                integrity_digest=opportunity.canonical_sha256(),
                available_at=cutoff,
            ),
        )
        sentence = ExplanationSentence(
            sentence_id=f"sentence.stub.{opportunity.opportunity_version_id}",
            template_id="template.opportunity.direction",
            bindings=(
                TemplateBinding(
                    name="direction",
                    value=opportunity.stance.value,
                ),
            ),
            evidence_references=(evidence_ref,),
            rendered_text=(
                f"AlphaLens detected a {opportunity.stance.value} signal "
                f"for {opportunity.scope.instrument}."
            ),
        )
        section = ExplanationSection(
            section_id="assessment",
            ordinal=1,
            sentences=(sentence,),
        )
        audit = AuditMetadata(
            created_at=cutoff,
            evidence_cutoff=cutoff,
            available_at=cutoff,
            provenance=Provenance(
                source_references=source_refs,
                policy_references=(policy,),
                code_version=_CODE_VERSION,
                configuration_hash="0" * 64,
                lineage_hash=canonical_sha256(source_refs),
            ),
            result_hash="0" * 64,
        )
        explanation = ExplanationArtifact(
            contract_version="1.0.0",
            explanation_id=(
                f"explanation.runtime.stub.{opportunity.opportunity_version_id}"
            ),
            opportunity_version_id=opportunity.opportunity_version_id,
            language="en",
            locale="en-US",
            taxonomy_version="1.0.0",
            template_set_version="1.0.0",
            sections=(section,),
            limitations=("explanation.stub",),
            audit=audit,
        )
        result_hash = canonical_sha256(
            explanation, exclude=frozenset({"result_hash"})
        )
        return dr(
            explanation,
            audit=dr(audit, result_hash=result_hash),
        )
