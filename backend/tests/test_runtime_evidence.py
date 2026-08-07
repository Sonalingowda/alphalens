"""Tests for the approved runtime evidence policy."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
    PipelineOutcome,
    PipelineRunRequest,
)
from app.opportunity_intelligence.persistence import (
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    MarketSnapshotMemoryRepository,
)
from app.opportunity_intelligence.repositories import (
    ScopedRepositoryQuery,
    StorageUnavailableError,
)
from app.opportunity_intelligence.services import (
    EvidenceService,
    ServiceUnavailableError,
)
from app.runtime_context import RuntimeMarketContextService
from app.runtime_detection import RuntimeOpportunityDetectionService
from app.runtime_evidence import (
    RUNTIME_EVIDENCE_POLICY_HASH,
    RUNTIME_EVIDENCE_POLICY_ID,
    RUNTIME_EVIDENCE_POLICY_VERSION,
    RuntimeEvidenceService,
)
from tests.test_opportunity_domain_models import (
    CUTOFF,
    _feature_snapshot,
    _market_snapshot,
)
from tests.test_runtime_detection import _feature, _feature_value


class RuntimeEvidenceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_buy_evidence_contains_policy_lineage_and_required_records(
        self,
    ) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )

        package = await fixture.service.assemble(
            fixture.candidate, fixture.market, fixture.feature, fixture.context
        )

        self.assertIsInstance(fixture.service, EvidenceService)
        self.assertEqual(
            package.package_id,
            f"evidence.runtime.ema_rsi.{fixture.candidate.candidate_id}",
        )
        self.assertEqual(
            package.audit.provenance.policy_references[0].policy_id,
            RUNTIME_EVIDENCE_POLICY_ID,
        )
        self.assertEqual(
            package.audit.provenance.policy_references[0].policy_version,
            RUNTIME_EVIDENCE_POLICY_VERSION,
        )
        self.assertEqual(
            package.audit.provenance.policy_references[0].integrity_digest,
            RUNTIME_EVIDENCE_POLICY_HASH,
        )
        self.assertEqual(
            {item.evidence_id.rsplit(".", 1)[-1] for item in package.items},
            {
                "market_price_close",
                "market_volume",
                "ema_12",
                "ema_26",
                "rsi",
                "atr_true_range",
                "ema_alignment",
                "rsi_state",
                "market_structure",
            },
        )
        self.assertEqual(package.limitations, ("confidence.unavailable",))

    async def test_sell_evidence_contains_sell_rsi_state(self) -> None:
        fixture = await _fixture(
            "99.000000000000000000", "100.000000000000000000", "45.000000000000000000"
        )

        package = await fixture.service.assemble(
            fixture.candidate, fixture.market, fixture.feature, fixture.context
        )

        rsi_state = next(
            item for item in package.items if item.evidence_id.endswith(".rsi_state")
        )
        self.assertEqual(rsi_state.observed_value, "sell_threshold_met")

    async def test_missing_required_source_is_unavailable_without_package(self) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _evidence_service(fixture, markets=MarketSnapshotMemoryRepository())

        with self.assertRaises(ServiceUnavailableError):
            await service.assemble(
                fixture.candidate, fixture.market, fixture.feature, fixture.context
            )
        self.assertEqual(len(fixture.evidence._records), 0)

    async def test_missing_feature_source_is_unavailable(self) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _evidence_service(fixture, features=FeatureSnapshotMemoryRepository())

        with self.assertRaises(ServiceUnavailableError):
            await service.assemble(
                fixture.candidate, fixture.market, fixture.feature, fixture.context
            )

    async def test_missing_context_source_is_unavailable(self) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _evidence_service(fixture, contexts=MarketContextMemoryRepository())

        with self.assertRaises(ServiceUnavailableError):
            await service.assemble(
                fixture.candidate, fixture.market, fixture.feature, fixture.context
            )

    async def test_stale_feature_timestamp_is_unavailable(self) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        stale_feature = replace(
            fixture.feature,
            snapshot_id="feature.snapshot.stale",
            values=tuple(
                replace(value, candle_timestamp=CUTOFF)
                for value in fixture.feature.values
            ),
        )
        await fixture.features.save(stale_feature)
        service = _evidence_service(fixture)

        with self.assertRaises(ServiceUnavailableError):
            await service.assemble(
                fixture.candidate, fixture.market, stale_feature, fixture.context
            )

    async def test_evidence_repository_failure_propagates(self) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        failing = SimpleNamespace(
            save=AsyncMock(
                side_effect=StorageUnavailableError("evidence store unavailable")
            )
        )
        service = _evidence_service(fixture, evidence=failing)

        with self.assertRaises(StorageUnavailableError):
            await service.assemble(
                fixture.candidate, fixture.market, fixture.feature, fixture.context
            )

    async def test_pipeline_returns_terminal_unavailable_before_assessment(
        self,
    ) -> None:
        fixture = await _fixture(
            "101.000000000000000000", "100.000000000000000000", "55.000000000000000000"
        )
        service = _evidence_service(fixture, markets=MarketSnapshotMemoryRepository())
        pipeline = OpportunityIntelligencePipeline(
            market_scanner=SimpleNamespace(scan=AsyncMock(return_value=fixture.market)),
            feature_snapshots=SimpleNamespace(
                resolve=AsyncMock(return_value=fixture.feature)
            ),
            market_contexts=SimpleNamespace(
                build=AsyncMock(return_value=fixture.context)
            ),
            detection=fixture.detector,
            evidence=service,
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
                run_id="evidence.pipeline.run.1",
                query=ScopedRepositoryQuery(
                    scope=fixture.market.scope, as_of=CUTOFF, limit=1
                ),
            )
        )

        self.assertIs(result.outcome, PipelineOutcome.UNAVAILABLE)
        self.assertEqual(result.stages[-1].reason_code, "evidence.unavailable")
        pipeline.assessment.assess.assert_not_awaited()  # type: ignore[attr-defined]


class _Fixture(SimpleNamespace):
    pass


async def _fixture(ema_12: str, ema_26: str, rsi: str) -> _Fixture:
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    detections = DetectionMemoryRepository()
    evidence = EvidenceMemoryRepository()
    market = replace(
        _market_snapshot(),
        scope=type(_market_snapshot().scope)(instrument="BTCUSDT", timeframe="5m"),
    )
    feature = _feature(ema_12, ema_26, rsi, market)
    atr = replace(
        _feature_value(
            _feature_snapshot().values[0],
            "average_true_range",
            "1.000000000000000000",
        ),
            output_name="average_true_range",
    )
    feature = replace(
        feature,
        values=tuple(sorted((*feature.values, atr), key=lambda item: item.value_id)),
    )
    await markets.save(market)
    await features.save(feature)
    context_service = RuntimeMarketContextService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        code_version="git:runtimeevidencecontext",
    )
    context = await context_service.build(market, feature)
    detector = RuntimeOpportunityDetectionService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        detections=detections,
        code_version="git:runtimeevidencedetection",
    )
    _, candidate = await detector.detect(market, feature, context)
    assert candidate is not None
    return _Fixture(
        markets=markets,
        features=features,
        contexts=contexts,
        detections=detections,
        evidence=evidence,
        market=market,
        feature=feature,
        context=context,
        candidate=candidate,
        detector=detector,
        service=_evidence_service(
            _Fixture(
                candidates=detections,
                markets=markets,
                features=features,
                contexts=contexts,
                detections=detections,
                evidence=evidence,
            )
        ),
    )


def _evidence_service(fixture: _Fixture, **overrides: object) -> RuntimeEvidenceService:
    return RuntimeEvidenceService(
        candidates=overrides.get("candidates") or fixture.detections,
        market_snapshots=overrides.get("markets") or fixture.markets,
        feature_snapshots=overrides.get("features") or fixture.features,
        market_contexts=overrides.get("contexts") or fixture.contexts,
        evidence=overrides.get("evidence") or fixture.evidence,
        code_version="git:runtimeevidence123",
    )
