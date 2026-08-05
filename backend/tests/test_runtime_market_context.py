"""Tests for repository-backed fail-closed runtime market context."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import (
    CandidateAttemptState,
    DetectionAttempt,
    IntegrityReference,
)
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineOutcome,
    PipelineRunRequest,
)
from app.opportunity_intelligence.persistence import (
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    MarketSnapshotMemoryRepository,
)
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.opportunity_intelligence.repositories import EntityId
from app.opportunity_intelligence.services import (
    MarketContextService,
    ServiceContractError,
)
from app.runtime_context import RuntimeMarketContextService
from tests.test_opportunity_domain_models import (
    CUTOFF,
    SCOPE,
    _audit,
    _feature_snapshot,
    _market_snapshot,
    _policy,
    _reference,
)


class RuntimeMarketContextServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_persists_descriptive_context_from_verified_inputs(self) -> None:
        markets, features, contexts, service, market, feature = await _service()

        context = await service.build(market, feature)

        self.assertIsInstance(service, MarketContextService)
        self.assertEqual(context.scope, SCOPE)
        self.assertEqual(context.context_timeframes, (SCOPE.timeframe,))
        self.assertTrue(context.data_quality.observations[0].value)
        self.assertEqual(
            tuple(
                component.status.value
                for component in (
                    context.trend,
                    context.momentum,
                    context.volatility,
                    context.structure,
                    context.session,
                )
            ),
            ("UNAVAILABLE",) * 5,
        )
        self.assertEqual(
            tuple(
                reference.artifact_id
                for reference in context.audit.provenance.source_references
            ),
            (market.snapshot_id, feature.snapshot_id),
        )
        restored = await contexts.get_by_id(EntityId(context.context_id))
        self.assertEqual(restored.canonical_json(), context.canonical_json())
        self.assertEqual(len(markets._records), 1)
        self.assertEqual(len(features._records), 1)

    async def test_rejects_unpersisted_or_mismatched_inputs(self) -> None:
        _, _, _, service, market, feature = await _service()

        with self.assertRaises(ServiceContractError):
            await service.build(
                replace(market, snapshot_id="market.snapshot.other"), feature
            )

    async def test_pipeline_accepts_service_through_existing_injection_port(
        self,
    ) -> None:
        _, _, contexts, service, market, feature = await _service()
        pipeline = OpportunityIntelligencePipeline(
            market_scanner=SimpleNamespace(scan=AsyncMock(return_value=market)),
            feature_snapshots=SimpleNamespace(resolve=AsyncMock(return_value=feature)),
            market_contexts=service,
            detection=SimpleNamespace(
                detect=AsyncMock(
                    return_value=(_not_detected_attempt(), None),
                )
            ),
            evidence=SimpleNamespace(assemble=AsyncMock()),
            assessment=SimpleNamespace(assess=AsyncMock()),
            qualification=SimpleNamespace(qualify=AsyncMock()),
            scoring=SimpleNamespace(score=AsyncMock()),
            ranking=SimpleNamespace(rank=AsyncMock()),
            lifecycle=SimpleNamespace(advance=AsyncMock()),
            notifications=SimpleNamespace(create_intents=AsyncMock()),
            dashboard=SimpleNamespace(project=AsyncMock()),
            indicators=SimpleNamespace(project=AsyncMock()),
            explanation=SimpleNamespace(explain=AsyncMock()),
            detail=SimpleNamespace(project=AsyncMock()),
        )

        result = await pipeline.run(
            PipelineRunRequest(
                run_id="context.pipeline.run.1",
                query=ScopedRepositoryQuery(scope=SCOPE, as_of=CUTOFF, limit=1),
            )
        )

        self.assertIs(result.outcome, PipelineOutcome.NO_CANDIDATE)
        self.assertEqual(
            result.market_context.context_id, f"context.runtime.{feature.snapshot_id}"
        )
        self.assertEqual(len(contexts._records), 1)


async def _service() -> tuple[
    MarketSnapshotMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    RuntimeMarketContextService,
    object,
    object,
]:
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    market = _market_snapshot()
    feature = _feature_snapshot()
    market_reference = IntegrityReference(
        artifact_id=market.snapshot_id,
        artifact_type="market_snapshot",
        artifact_version="1.0.0",
        integrity_digest=market.canonical_sha256(),
        available_at=market.audit.available_at,
    )
    feature = replace(feature, market_snapshot=market_reference)
    await markets.save(market)
    await features.save(feature)
    return (
        markets,
        features,
        contexts,
        RuntimeMarketContextService(
            market_snapshots=markets,
            feature_snapshots=features,
            market_contexts=contexts,
            code_version="git:runtimecontext123",
        ),
        market,
        feature,
    )


def _not_detected_attempt() -> DetectionAttempt:
    source = _reference("context.detection.source")
    return DetectionAttempt(
        contract_version="1.0.0",
        attempt_id="context.detection.attempt.1",
        scope=SCOPE,
        state=CandidateAttemptState.NOT_DETECTED,
        detection_policy=_policy("policy.context.detection"),
        input_references=(source,),
        reason_codes=("detection.not_configured",),
        candidate_id=None,
        audit=_audit(source),
    )
