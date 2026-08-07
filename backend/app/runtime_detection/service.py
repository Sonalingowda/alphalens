"""Repository-backed implementation of the approved runtime detection policy."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    CandidateAttemptState,
    ContextStatus,
    DetectionAttempt,
    FeatureSnapshot,
    FeatureSnapshotValue,
    IntegrityReference,
    MarketContext,
    MarketSnapshot,
    OpportunityCandidate,
    PolicyReference,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    DetectionRepository,
    EntityId,
    FeatureSnapshotRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
)
from app.opportunity_intelligence.services import ServiceContractError


RUNTIME_DETECTION_POLICY_ID = "alphalens_runtime_detection_ema_rsi"
RUNTIME_DETECTION_POLICY_VERSION = "1.0.0"
RUNTIME_DETECTION_POLICY_HASH = (
    "d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a"
)
_CONTRACT_VERSION = "1.0.0"
_INSTRUMENT = "BTCUSDT"
_TIMEFRAMES = ("5m", "10m", "15m")
_BUY_RSI_MINIMUM = "55.000000000000000000"
_SELL_RSI_MAXIMUM = "45.000000000000000000"
_REQUIRED_FEATURES = (
    ("exponential_moving_average_12", "1.0.0", "exponential_moving_average_12"),
    ("exponential_moving_average_26", "1.0.0", "exponential_moving_average_26"),
    ("relative_strength_index", "1.0.0", "relative_strength_index"),
)


@dataclass(frozen=True, slots=True)
class _PersistedInputs:
    market: MarketSnapshot
    features: FeatureSnapshot
    context: MarketContext
    references: tuple[IntegrityReference, IntegrityReference, IntegrityReference]
    cutoff: datetime


class RuntimeOpportunityDetectionService:
    """Evaluate only the immutable POLICY-001 EMA/RSI detection conditions."""

    def __init__(
        self,
        *,
        market_snapshots: MarketSnapshotRepository,
        feature_snapshots: FeatureSnapshotRepository,
        market_contexts: MarketContextRepository,
        detections: DetectionRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime detection code version must be non-empty.")
        self._market_snapshots = market_snapshots
        self._feature_snapshots = feature_snapshots
        self._market_contexts = market_contexts
        self._detections = detections
        self._code_version = code_version

    async def detect(
        self,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
        market_context: MarketContext,
    ) -> tuple[DetectionAttempt, OpportunityCandidate | None]:
        """Persist the policy-mandated terminal attempt and optional candidate."""
        inputs = await self._load_persisted_inputs(
            market_snapshot,
            feature_snapshot,
            market_context,
        )
        error = _validate_inputs(inputs)
        if error is not None:
            attempt = _attempt(
                inputs,
                CandidateAttemptState.UNAVAILABLE,
                "detection.input_unavailable",
                None,
                self._code_version,
            )
            return await self._detections.save_attempt(attempt), None

        values = _required_values(inputs.features)
        ema_12 = values[_REQUIRED_FEATURES[0]]
        ema_26 = values[_REQUIRED_FEATURES[1]]
        rsi = values[_REQUIRED_FEATURES[2]]
        candidate_id = _candidate_id(inputs.market)
        if ema_12.value > ema_26.value and rsi.value >= _decimal(_BUY_RSI_MINIMUM):
            candidate = _candidate(
                inputs,
                candidate_id,
                (
                    "detection.persisted_inputs_verified",
                    "detection.ema12_above_ema26",
                    "detection.rsi_ge_55",
                ),
                self._code_version,
            )
            attempt = _attempt(
                inputs,
                CandidateAttemptState.DETECTED,
                candidate.reason_codes,
                candidate.candidate_id,
                self._code_version,
            )
            await self._detections.save_attempt(attempt)
            return attempt, await self._detections.save_candidate(candidate)
        if ema_12.value < ema_26.value and rsi.value <= _decimal(_SELL_RSI_MAXIMUM):
            candidate = _candidate(
                inputs,
                candidate_id,
                (
                    "detection.persisted_inputs_verified",
                    "detection.ema12_below_ema26",
                    "detection.rsi_le_45",
                ),
                self._code_version,
            )
            attempt = _attempt(
                inputs,
                CandidateAttemptState.DETECTED,
                candidate.reason_codes,
                candidate.candidate_id,
                self._code_version,
            )
            await self._detections.save_attempt(attempt)
            return attempt, await self._detections.save_candidate(candidate)

        attempt = _attempt(
            inputs,
            CandidateAttemptState.NOT_DETECTED,
            "detection.conditions_not_met",
            None,
            self._code_version,
        )
        return await self._detections.save_attempt(attempt), None

    async def _load_persisted_inputs(
        self,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
        market_context: MarketContext,
    ) -> _PersistedInputs:
        market = await self._market_snapshots.get_by_id(
            EntityId(market_snapshot.snapshot_id)
        )
        features = await self._feature_snapshots.get_by_id(
            EntityId(feature_snapshot.snapshot_id)
        )
        context = await self._market_contexts.get_by_id(
            EntityId(market_context.context_id)
        )
        if market.canonical_sha256() != market_snapshot.canonical_sha256():
            raise ServiceContractError(
                "Persisted market snapshot conflicts with input."
            )
        if features.canonical_sha256() != feature_snapshot.canonical_sha256():
            raise ServiceContractError(
                "Persisted feature snapshot conflicts with input."
            )
        if context.canonical_sha256() != market_context.canonical_sha256():
            raise ServiceContractError("Persisted market context conflicts with input.")
        references = (
            _reference(market.snapshot_id, "market_snapshot", market),
            _reference(features.snapshot_id, "feature_snapshot", features),
            _reference(context.context_id, "market_context", context),
        )
        return _PersistedInputs(
            market=market,
            features=features,
            context=context,
            references=references,
            cutoff=max(reference.available_at for reference in references),
        )


def _validate_inputs(inputs: _PersistedInputs) -> str | None:
    market, features, context = inputs.market, inputs.features, inputs.context
    if (
        market.scope.instrument != _INSTRUMENT
        or market.scope.timeframe not in _TIMEFRAMES
        or features.scope != market.scope
        or context.scope != market.scope
        or context.context_timeframes != (market.scope.timeframe,)
        or not market.complete
        or len(market.candles) != 1
    ):
        return "scope_or_market"
    candle = market.candles[0]
    if (
        features.market_snapshot.artifact_id != market.snapshot_id
        or features.market_snapshot.integrity_digest != market.canonical_sha256()
        or features.market_snapshot.available_at > inputs.cutoff
        or context.data_quality.status is not ContextStatus.AVAILABLE
        or len(context.data_quality.observations) != 1
        or context.data_quality.observations[0].semantic_identifier
        != "data_quality.persisted_inputs_verified"
        or context.data_quality.observations[0].value is not True
        or context.data_quality.observations[0].time_start != candle.timestamp
        or context.data_quality.observations[0].time_end != candle.timestamp
        or any(
            component.status is not ContextStatus.UNAVAILABLE
            for component in (
                context.trend,
                context.momentum,
                context.volatility,
                context.structure,
                context.session,
            )
        )
    ):
        return "lineage_or_context"
    context_sources = context.audit.provenance.source_references
    if {
        (reference.artifact_id, reference.integrity_digest)
        for reference in context_sources
    } != {
        (inputs.references[0].artifact_id, inputs.references[0].integrity_digest),
        (inputs.references[1].artifact_id, inputs.references[1].integrity_digest),
    }:
        return "context_provenance"
    try:
        values = _required_values(features)
    except ServiceContractError:
        return "required_feature"
    if any(
        value.candle_timestamp != candle.timestamp or value.available_at > inputs.cutoff
        for value in values.values()
    ):
        return "feature_freshness"
    return None


def _required_values(
    features: FeatureSnapshot,
) -> dict[tuple[str, str, str], FeatureSnapshotValue]:
    values = {
        (item.feature_identifier, item.definition_version, item.output_name): item
        for item in features.values
        if (item.feature_identifier, item.definition_version, item.output_name)
        in _REQUIRED_FEATURES
    }
    if len(values) != len(_REQUIRED_FEATURES):
        raise ServiceContractError("Detection requires every approved feature value.")
    return values


def _reference(
    artifact_id: str,
    artifact_type: str,
    entity: MarketSnapshot | FeatureSnapshot | MarketContext,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version=_CONTRACT_VERSION,
        integrity_digest=entity.canonical_sha256(),
        available_at=entity.audit.available_at,
    )


def _policy() -> PolicyReference:
    return PolicyReference(
        policy_id=RUNTIME_DETECTION_POLICY_ID,
        policy_version=RUNTIME_DETECTION_POLICY_VERSION,
        integrity_digest=RUNTIME_DETECTION_POLICY_HASH,
    )


def _candidate_id(market: MarketSnapshot) -> str:
    timestamp = market.candles[0].timestamp
    milliseconds = int(timestamp.timestamp()) * 1000 + timestamp.microsecond // 1000
    return (
        "candidate.runtime_detection_ema_rsi."
        f"{market.scope.instrument}.{market.scope.timeframe}.{milliseconds}"
    )


def _attempt(
    inputs: _PersistedInputs,
    state: CandidateAttemptState,
    reason_codes: str | tuple[str, ...],
    candidate_id: str | None,
    code_version: str,
) -> DetectionAttempt:
    reasons = (reason_codes,) if isinstance(reason_codes, str) else reason_codes
    attempt_id = (
        "detection.attempt.runtime_detection_ema_rsi."
        f"{inputs.market.scope.instrument}.{inputs.market.scope.timeframe}."
        f"{int(inputs.market.candles[0].timestamp.timestamp() * 1000)}"
    )
    result_hash = canonical_sha256(
        {
            "attempt_id": attempt_id,
            "state": state,
            "candidate_id": candidate_id,
            "reasons": reasons,
            "inputs": inputs.references,
        }
    )
    return DetectionAttempt(
        contract_version=_CONTRACT_VERSION,
        attempt_id=attempt_id,
        scope=inputs.market.scope,
        state=state,
        detection_policy=_policy(),
        input_references=inputs.references,
        reason_codes=reasons,
        candidate_id=candidate_id,
        audit=_audit(inputs, result_hash, code_version),
    )


def _candidate(
    inputs: _PersistedInputs,
    candidate_id: str,
    reason_codes: tuple[str, ...],
    code_version: str,
) -> OpportunityCandidate:
    result_hash = canonical_sha256(
        {
            "candidate_id": candidate_id,
            "policy": _policy(),
            "references": inputs.references,
            "reason_codes": reason_codes,
        }
    )
    return OpportunityCandidate(
        contract_version=_CONTRACT_VERSION,
        candidate_id=candidate_id,
        scope=inputs.market.scope,
        detected_at=inputs.cutoff,
        detection_policy=_policy(),
        market_snapshot_reference=inputs.references[0],
        feature_snapshot_reference=inputs.references[1],
        context_reference=inputs.references[2],
        reason_codes=reason_codes,
        evidence_references=inputs.references,
        limitations=(),
        audit=_audit(inputs, result_hash, code_version),
    )


def _audit(
    inputs: _PersistedInputs,
    result_hash: str,
    code_version: str,
) -> AuditMetadata:
    lineage_hash = canonical_sha256(inputs.references)
    return AuditMetadata(
        created_at=inputs.cutoff,
        evidence_cutoff=inputs.cutoff,
        available_at=inputs.cutoff,
        provenance=Provenance(
            source_references=inputs.references,
            policy_references=(_policy(),),
            code_version=code_version,
            configuration_hash=RUNTIME_DETECTION_POLICY_HASH,
            lineage_hash=lineage_hash,
        ),
        result_hash=result_hash,
    )


def _decimal(value: str) -> Decimal:
    return Decimal(value)
