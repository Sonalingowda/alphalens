"""Repository-backed descriptive market context without decision semantics."""

from datetime import datetime

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ContextCategory,
    ContextComponent,
    ContextObservation,
    ContextStatus,
    FeatureSnapshot,
    IntegrityReference,
    MarketContext,
    MarketSnapshot,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
    FeatureSnapshotRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
)
from app.opportunity_intelligence.services import ServiceContractError


RUNTIME_CONTEXT_SERVICE_VERSION = "1.0.0"
_CONTEXT_CONTRACT_VERSION = "1.0.0"
_UNAVAILABLE_LIMITATION = "definition.unavailable"
_DATA_QUALITY_DEFINITION_ID = "context.data_quality.persisted_inputs"
_UNAVAILABLE_DEFINITION_IDS = {
    ContextCategory.TREND: "context.trend.unavailable",
    ContextCategory.MOMENTUM: "context.momentum.unavailable",
    ContextCategory.VOLATILITY: "context.volatility.unavailable",
    ContextCategory.STRUCTURE: "context.structure.unavailable",
    ContextCategory.SESSION: "context.session.unavailable",
}
_DEFINITION_SET_HASH = canonical_sha256(
    {
        "version": RUNTIME_CONTEXT_SERVICE_VERSION,
        "definitions": {
            category.value: definition_id
            for category, definition_id in _UNAVAILABLE_DEFINITION_IDS.items()
        }
        | {ContextCategory.DATA_QUALITY.value: _DATA_QUALITY_DEFINITION_ID},
    }
)
_CONFIGURATION_HASH = canonical_sha256(
    {
        "service_version": RUNTIME_CONTEXT_SERVICE_VERSION,
        "definition_set_hash": _DEFINITION_SET_HASH,
    }
)


class RuntimeMarketContextService:
    """Persist a descriptive context from verified immutable runtime inputs.

    The frozen context contract requires components without approved quantitative
    definitions to remain unavailable.  This adapter therefore records only
    input-persistence integrity as an available data-quality observation.
    """

    def __init__(
        self,
        *,
        market_snapshots: MarketSnapshotRepository,
        feature_snapshots: FeatureSnapshotRepository,
        market_contexts: MarketContextRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime context code version must be non-empty.")
        self._market_snapshots = market_snapshots
        self._feature_snapshots = feature_snapshots
        self._market_contexts = market_contexts
        self._code_version = code_version

    async def build(
        self,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
    ) -> MarketContext:
        """Verify persisted inputs, then append their descriptive context."""
        market, features = await self._verify_persisted_inputs(
            market_snapshot,
            feature_snapshot,
        )
        market_reference = _reference(
            market.snapshot_id,
            "market_snapshot",
            market.canonical_sha256(),
            market.audit.available_at,
        )
        feature_reference = _reference(
            features.snapshot_id,
            "feature_snapshot",
            features.canonical_sha256(),
            features.audit.available_at,
        )
        references = (market_reference, feature_reference)
        available_at = max(reference.available_at for reference in references)
        time_start = market.candles[0].timestamp
        time_end = market.candles[-1].timestamp
        data_quality = ContextComponent(
            category=ContextCategory.DATA_QUALITY,
            definition_id=_DATA_QUALITY_DEFINITION_ID,
            definition_version=RUNTIME_CONTEXT_SERVICE_VERSION,
            status=ContextStatus.AVAILABLE,
            observations=(
                ContextObservation(
                    observation_id=(
                        "context.data_quality.persisted_inputs_verified."
                        f"{features.snapshot_id}"
                    ),
                    semantic_identifier="data_quality.persisted_inputs_verified",
                    value=True,
                    unit=None,
                    time_start=time_start,
                    time_end=time_end,
                    available_at=available_at,
                    source_references=references,
                ),
            ),
            evidence_references=references,
            available_at=available_at,
        )
        components = {
            category: _unavailable_component(category, available_at)
            for category in _UNAVAILABLE_DEFINITION_IDS
        }
        context_id = f"context.runtime.{features.snapshot_id}"
        lineage_hash = canonical_sha256(
            {
                "market_snapshot": market_reference.integrity_digest,
                "feature_snapshot": feature_reference.integrity_digest,
            }
        )
        result_hash = canonical_sha256(
            {
                "context_id": context_id,
                "scope": market.scope,
                "definition_set_hash": _DEFINITION_SET_HASH,
                "components": tuple(components.values()) + (data_quality,),
                "lineage_hash": lineage_hash,
            }
        )
        context = MarketContext(
            contract_version=_CONTEXT_CONTRACT_VERSION,
            context_id=context_id,
            scope=market.scope,
            context_timeframes=(market.scope.timeframe,),
            trend=components[ContextCategory.TREND],
            momentum=components[ContextCategory.MOMENTUM],
            volatility=components[ContextCategory.VOLATILITY],
            structure=components[ContextCategory.STRUCTURE],
            session=components[ContextCategory.SESSION],
            data_quality=data_quality,
            definition_set_hash=_DEFINITION_SET_HASH,
            audit=AuditMetadata(
                created_at=available_at,
                evidence_cutoff=available_at,
                available_at=available_at,
                provenance=Provenance(
                    source_references=references,
                    policy_references=(),
                    code_version=self._code_version,
                    configuration_hash=_CONFIGURATION_HASH,
                    lineage_hash=lineage_hash,
                ),
                result_hash=result_hash,
            ),
        )
        return await self._market_contexts.save(context)

    async def _verify_persisted_inputs(
        self,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
    ) -> tuple[MarketSnapshot, FeatureSnapshot]:
        if market_snapshot.scope != feature_snapshot.scope:
            raise ServiceContractError("Market and feature snapshot scopes must match.")
        try:
            market = await self._market_snapshots.get_by_id(
                EntityId(market_snapshot.snapshot_id)
            )
            features = await self._feature_snapshots.get_by_id(
                EntityId(feature_snapshot.snapshot_id)
            )
        except EntityNotFoundError as error:
            raise ServiceContractError(
                "Market context requires persisted market and feature snapshots."
            ) from error
        if market.canonical_sha256() != market_snapshot.canonical_sha256():
            raise ServiceContractError(
                "Persisted market snapshot conflicts with input."
            )
        if features.canonical_sha256() != feature_snapshot.canonical_sha256():
            raise ServiceContractError(
                "Persisted feature snapshot conflicts with input."
            )
        if (
            features.market_snapshot.artifact_id != market.snapshot_id
            or features.market_snapshot.integrity_digest != market.canonical_sha256()
        ):
            raise ServiceContractError(
                "Feature snapshot does not reference the persisted market snapshot."
            )
        return market, features


def _reference(
    artifact_id: str,
    artifact_type: str,
    integrity_digest: str,
    available_at: datetime,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version=_CONTEXT_CONTRACT_VERSION,
        integrity_digest=integrity_digest,
        available_at=available_at,
    )


def _unavailable_component(
    category: ContextCategory,
    available_at: datetime,
) -> ContextComponent:
    return ContextComponent(
        category=category,
        definition_id=_UNAVAILABLE_DEFINITION_IDS[category],
        definition_version=RUNTIME_CONTEXT_SERVICE_VERSION,
        status=ContextStatus.UNAVAILABLE,
        observations=(),
        evidence_references=(),
        available_at=available_at,
        limitations=(_UNAVAILABLE_LIMITATION,),
    )
