"""Tests for the approved repository-backed runtime detection policy."""

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.domain import (
    FeatureSnapshotValue,
    IntegrityReference,
    MarketScope,
)
from app.opportunity_intelligence.persistence import (
    DetectionMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    MarketSnapshotMemoryRepository,
)
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineOutcome,
    PipelineRunRequest,
)
from app.opportunity_intelligence.repositories import (
    ScopedRepositoryQuery,
    StorageUnavailableError,
)
from app.opportunity_intelligence.services import OpportunityDetectionService
from app.runtime_context import RuntimeMarketContextService
from app.runtime_detection import (
    RUNTIME_DETECTION_POLICY_HASH,
    RUNTIME_DETECTION_POLICY_ID,
    RUNTIME_DETECTION_POLICY_VERSION,
    RuntimeOpportunityDetectionService,
)
from tests.test_opportunity_domain_models import (
    CUTOFF,
    HASH_A,
    _feature_snapshot,
    _market_snapshot,
)


class RuntimeOpportunityDetectionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_buy_condition_persists_detected_attempt_and_candidate(self) -> None:
        service, detections, market, feature, context = await _service(
            ema_12="101.000000000000000000",
            ema_26="100.000000000000000000",
            rsi="55.000000000000000000",
        )

        attempt, candidate = await service.detect(market, feature, context)

        self.assertIsInstance(service, OpportunityDetectionService)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(attempt.state.value, "DETECTED")
        self.assertEqual(
            candidate.detection_policy.policy_id, RUNTIME_DETECTION_POLICY_ID
        )
        self.assertEqual(
            candidate.detection_policy.policy_version,
            RUNTIME_DETECTION_POLICY_VERSION,
        )
        self.assertEqual(
            candidate.detection_policy.integrity_digest,
            RUNTIME_DETECTION_POLICY_HASH,
        )
        self.assertEqual(
            candidate.reason_codes,
            (
                "detection.persisted_inputs_verified",
                "detection.ema12_above_ema26",
                "detection.rsi_ge_55",
            ),
        )
        self.assertEqual(len(detections._attempts._records), 1)
        self.assertEqual(len(detections._candidates._records), 1)

    async def test_sell_condition_persists_detected_attempt_and_candidate(self) -> None:
        service, detections, market, feature, context = await _service(
            ema_12="99.000000000000000000",
            ema_26="100.000000000000000000",
            rsi="45.000000000000000000",
        )

        attempt, candidate = await service.detect(market, feature, context)

        self.assertEqual(attempt.state.value, "DETECTED")
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(
            candidate.reason_codes[-2:],
            ("detection.ema12_below_ema26", "detection.rsi_le_45"),
        )
        self.assertEqual(len(detections._candidates._records), 1)

    async def test_no_candidate_persists_not_detected_attempt_only(self) -> None:
        service, detections, market, feature, context = await _service(
            ema_12="101.000000000000000000",
            ema_26="100.000000000000000000",
            rsi="50.000000000000000000",
        )

        attempt, candidate = await service.detect(market, feature, context)

        self.assertEqual(attempt.state.value, "NOT_DETECTED")
        self.assertIsNone(candidate)
        self.assertEqual(attempt.reason_codes, ("detection.conditions_not_met",))
        self.assertEqual(len(detections._attempts._records), 1)
        self.assertEqual(len(detections._candidates._records), 0)

    async def test_stale_input_persists_unavailable_attempt(self) -> None:
        service, detections, market, feature, context = await _service(
            ema_12="101.000000000000000000",
            ema_26="100.000000000000000000",
            rsi="55.000000000000000000",
            stale_context=True,
        )

        attempt, candidate = await service.detect(market, feature, context)

        self.assertEqual(attempt.state.value, "UNAVAILABLE")
        self.assertEqual(attempt.reason_codes, ("detection.input_unavailable",))
        self.assertIsNone(candidate)
        self.assertEqual(len(detections._candidates._records), 0)

    async def test_missing_feature_persists_unavailable_attempt(self) -> None:
        service, detections, market, feature, context = await _service(
            ema_12="101.000000000000000000",
            ema_26="100.000000000000000000",
            rsi=None,
        )

        attempt, candidate = await service.detect(market, feature, context)

        self.assertEqual(attempt.state.value, "UNAVAILABLE")
        self.assertEqual(attempt.reason_codes, ("detection.input_unavailable",))
        self.assertIsNone(candidate)
        self.assertEqual(len(detections._candidates._records), 0)

    async def test_repository_failure_propagates_without_candidate(self) -> None:
        service, _, market, feature, context = await _service(
            ema_12="101.000000000000000000",
            ema_26="100.000000000000000000",
            rsi="50.000000000000000000",
            detections=type(
                "FailingDetections",
                (),
                {
                    "save_attempt": AsyncMock(
                        side_effect=StorageUnavailableError("down")
                    )
                },
            )(),
        )

        with self.assertRaises(StorageUnavailableError):
            await service.detect(market, feature, context)

    async def test_pipeline_uses_detector_through_existing_dependency_injection(
        self,
    ) -> None:
        service, detections, market, feature, context = await _service(
            ema_12="101.000000000000000000",
            ema_26="100.000000000000000000",
            rsi="50.000000000000000000",
        )
        pipeline = OpportunityIntelligencePipeline(
            market_scanner=SimpleNamespace(scan=AsyncMock(return_value=market)),
            feature_snapshots=SimpleNamespace(resolve=AsyncMock(return_value=feature)),
            market_contexts=SimpleNamespace(build=AsyncMock(return_value=context)),
            detection=service,
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
                run_id="detection.pipeline.run.1",
                query=ScopedRepositoryQuery(
                    scope=market.scope,
                    as_of=CUTOFF,
                    limit=1,
                ),
            )
        )

        self.assertIs(result.outcome, PipelineOutcome.NO_CANDIDATE)
        self.assertEqual(len(detections._attempts._records), 1)
        pipeline.evidence.assemble.assert_not_awaited()  # type: ignore[attr-defined]


async def _service(
    *,
    ema_12: str,
    ema_26: str,
    rsi: str | None,
    stale_context: bool = False,
    detections: object | None = None,
):
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    market = replace(
        _market_snapshot(),
        scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
    )
    feature = _feature(ema_12, ema_26, rsi, market)
    await markets.save(market)
    await features.save(feature)
    context_service = RuntimeMarketContextService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        code_version="git:runtimedetectioncontext",
    )
    context = await context_service.build(market, feature)
    if stale_context:
        observation = replace(
            context.data_quality.observations[0],
            time_end=CUTOFF,
        )
        context = replace(
            context,
            context_id=f"{context.context_id}.stale",
            data_quality=replace(context.data_quality, observations=(observation,)),
        )
        await contexts.save(context)
    repository = detections or DetectionMemoryRepository()
    service = RuntimeOpportunityDetectionService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        detections=repository,  # type: ignore[arg-type]
        code_version="git:runtimedetection123",
    )
    return service, repository, market, feature, context


def _feature(
    ema_12: str,
    ema_26: str,
    rsi: str | None,
    market,
):
    source = _feature_snapshot().values[0]
    values = [
        _feature_value(source, "exponential_moving_average_12", ema_12),
        _feature_value(source, "exponential_moving_average_26", ema_26),
    ]
    if rsi is not None:
        values.append(_feature_value(source, "relative_strength_index", rsi))
    market_reference = IntegrityReference(
        artifact_id=market.snapshot_id,
        artifact_type="market_snapshot",
        artifact_version="1.0.0",
        integrity_digest=market.canonical_sha256(),
        available_at=market.audit.available_at,
    )
    return replace(
        _feature_snapshot(),
        scope=market.scope,
        market_snapshot=market_reference,
        values=tuple(sorted(values, key=lambda item: item.value_id)),
    )


def _feature_value(
    source: FeatureSnapshotValue,
    identifier: str,
    value: str,
) -> FeatureSnapshotValue:
    return replace(
        source,
        feature_identifier=identifier,
        output_name=identifier,
        value=Decimal(value),
        feature_record=IntegrityReference(
            artifact_id=f"feature.record.{identifier}",
            artifact_type="runtime_feature_value",
            artifact_version="1.0.0",
            integrity_digest=HASH_A,
            available_at=source.available_at,
        ),
    )
