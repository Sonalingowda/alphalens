"""Deterministic in-memory orchestration for approved intraday features."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from uuid import UUID

from app.features.contracts import (
    FEATURE_AVAILABILITY_CONTRACT_VERSION,
    INTRADAY_TIMEFRAMES,
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureDependencyInput,
    FeatureDefinitionMetadata,
    FeatureHistoryType,
    FeatureValue,
    feature_available_at,
    quantize_feature_value,
)
from app.features.registry import (
    INTRADAY_FEATURE_REGISTRY,
)
from app.features.atr import ATR_FEATURE_DEFINITIONS
from app.features.ema import EMA_FEATURE_DEFINITIONS
from app.features.rsi import RSI_FEATURE_DEFINITIONS
from app.features.tier_a import (
    TIER_A_FEATURE_DEFINITIONS,
    IntradayFeatureDefinition,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import (
    floor_timeframe_boundary,
    timeframe_duration,
)


LEGACY_INTRADAY_PIPELINE_VERSION = "2.0.0"
ATR_INTRADAY_PIPELINE_VERSION = "2.1.0"
EMA_INTRADAY_PIPELINE_VERSION = "2.2.0"
RSI_INTRADAY_PIPELINE_VERSION = "2.3.0"
INTRADAY_PIPELINE_VERSION = "2.4.0"


@dataclass(frozen=True, slots=True)
class SourceCandleObservation:
    candle: Candle
    ingestion_batch_id: UUID
    is_complete: bool


@dataclass(frozen=True, slots=True)
class IntradaySourceSnapshot:
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    observations: tuple[SourceCandleObservation, ...]
    source_ingestion_batch_ids: tuple[UUID, ...]
    range_start: datetime
    range_end: datetime
    data_hash: str
    provenance_hash: str

    @property
    def candles(self) -> tuple[Candle, ...]:
        return tuple(observation.candle for observation in self.observations)


@dataclass(frozen=True, slots=True)
class PipelineFeatureValue:
    feature_identifier: str
    definition_version: str
    output_name: str
    candle_timestamp: datetime
    available_at: datetime
    value: Decimal


@dataclass(frozen=True, slots=True)
class PipelineFeatureDependency:
    consumer_feature_identifier: str
    consumer_definition_version: str
    consumer_output_name: str
    consumer_candle_timestamp: datetime
    dependency_ordinal: int
    dependency_feature_identifier: str
    dependency_definition_version: str
    dependency_output_name: str
    dependency_candle_timestamp: datetime
    dependency_available_at: datetime
    dependency_value: Decimal


@dataclass(frozen=True, slots=True)
class SourceBatchEvidence:
    ingestion_batch_id: UUID
    source_candle_count: int
    range_start: datetime
    range_end: datetime
    source_subset_hash: str


@dataclass(frozen=True, slots=True)
class IntradayFeaturePipelineResult:
    pipeline_version: str
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    source_data_hash: str
    source_provenance_hash: str
    source_ingestion_batch_ids: tuple[UUID, ...]
    registry_hash: str
    registry_schema_version: str
    availability_contract_version: str
    execution_order: tuple[str, ...]
    values: tuple[PipelineFeatureValue, ...]
    dependency_memberships: tuple[PipelineFeatureDependency, ...]
    point_in_time_validated: bool
    result_hash: str


def build_intraday_source_snapshot(
    *,
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
    observations: tuple[SourceCandleObservation, ...],
) -> IntradaySourceSnapshot:
    if asset_identifier != "BTC" or quote_currency != "USD":
        raise FeatureComputationError("Phase 3 source snapshots support only BTC/USD.")
    _validate_source_observations(observations, timeframe)

    timestamps = tuple(
        _required_timestamp(observation.candle.timestamp)
        for observation in observations
    )
    source_batch_ids = tuple(
        sorted(
            {observation.ingestion_batch_id for observation in observations},
            key=str,
        )
    )
    return IntradaySourceSnapshot(
        asset_identifier=asset_identifier,
        quote_currency=quote_currency,
        timeframe=timeframe,
        observations=observations,
        source_ingestion_batch_ids=source_batch_ids,
        range_start=timestamps[0],
        range_end=timestamps[-1],
        data_hash=_snapshot_data_hash(
            asset_identifier,
            quote_currency,
            timeframe,
            observations,
        ),
        provenance_hash=_snapshot_provenance_hash(
            asset_identifier,
            quote_currency,
            timeframe,
            observations,
        ),
    )


def run_intraday_feature_pipeline(
    snapshot: IntradaySourceSnapshot,
) -> IntradayFeaturePipelineResult:
    _verify_snapshot_integrity(snapshot)
    definitions = _approved_definitions_by_identifier()
    output_order = {
        name: index for index, name in enumerate(INTRADAY_FEATURE_REGISTRY.output_names)
    }
    executed: set[str] = set()
    execution_order: list[str] = []
    pipeline_values: list[PipelineFeatureValue] = []
    dependency_memberships: list[PipelineFeatureDependency] = []
    computed_values: dict[str, tuple[FeatureValue, ...]] = {}
    pipeline_value_lookup: dict[
        tuple[str, str, str, datetime], PipelineFeatureValue
    ] = {}

    for metadata in INTRADAY_FEATURE_REGISTRY.definitions:
        missing_dependencies = set(metadata.dependencies) - executed
        if missing_dependencies:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} has unexecuted dependencies."
            )
        definition = definitions.get(metadata.identifier)
        if definition is None or definition.metadata != metadata:
            raise FeatureComputationError(
                f"Feature implementation does not match registered metadata "
                f"for {metadata.identifier}."
            )
        dependency_inputs = _dependency_inputs(
            metadata,
            computed_values,
            INTRADAY_FEATURE_REGISTRY.definitions,
        )
        raw_values = definition.compute(
            snapshot.candles,
            snapshot.timeframe,
            dependency_inputs,
        )
        _validate_feature_output(
            metadata,
            raw_values,
            snapshot,
        )
        _verify_prefix_invariance(
            definition,
            raw_values,
            snapshot,
            dependency_inputs,
        )
        current_pipeline_values = tuple(
            PipelineFeatureValue(
                feature_identifier=metadata.identifier,
                definition_version=metadata.definition_version,
                output_name=value.feature_name,
                candle_timestamp=value.timestamp,
                available_at=feature_available_at(
                    value.timestamp,
                    snapshot.timeframe,
                    metadata.availability_rule,
                ),
                value=value.value,
            )
            for value in raw_values
        )
        dependency_memberships.extend(
            _feature_dependency_memberships(
                metadata,
                raw_values,
                pipeline_value_lookup
                | {
                    (
                        value.feature_identifier,
                        value.definition_version,
                        value.output_name,
                        value.candle_timestamp,
                    ): value
                    for value in current_pipeline_values
                },
            )
        )
        pipeline_values.extend(current_pipeline_values)
        for value in current_pipeline_values:
            pipeline_value_lookup[
                (
                    value.feature_identifier,
                    value.definition_version,
                    value.output_name,
                    value.candle_timestamp,
                )
            ] = value
        computed_values[metadata.identifier] = raw_values
        executed.add(metadata.identifier)
        execution_order.append(metadata.identifier)

    pipeline_values.sort(
        key=lambda value: (
            value.candle_timestamp,
            output_order[value.output_name],
        )
    )
    values = tuple(pipeline_values)
    dependency_memberships.sort(
        key=lambda membership: (
            membership.consumer_candle_timestamp,
            output_order[membership.consumer_output_name],
            membership.dependency_ordinal,
        )
    )
    dependencies = tuple(dependency_memberships)
    _validate_pipeline_values(values, snapshot)
    _validate_pipeline_dependencies(dependencies, values)
    result_hash = _pipeline_result_hash(
        snapshot=snapshot,
        execution_order=tuple(execution_order),
        values=values,
        dependency_memberships=dependencies,
    )
    return IntradayFeaturePipelineResult(
        pipeline_version=INTRADAY_PIPELINE_VERSION,
        asset_identifier=snapshot.asset_identifier,
        quote_currency=snapshot.quote_currency,
        timeframe=snapshot.timeframe,
        source_data_hash=snapshot.data_hash,
        source_provenance_hash=snapshot.provenance_hash,
        source_ingestion_batch_ids=(snapshot.source_ingestion_batch_ids),
        registry_hash=INTRADAY_FEATURE_REGISTRY.configuration_hash,
        registry_schema_version=INTRADAY_FEATURE_REGISTRY.schema_version,
        availability_contract_version=(FEATURE_AVAILABILITY_CONTRACT_VERSION),
        execution_order=tuple(execution_order),
        values=values,
        dependency_memberships=dependencies,
        point_in_time_validated=True,
        result_hash=result_hash,
    )


def source_batch_evidence(
    snapshot: IntradaySourceSnapshot,
) -> tuple[SourceBatchEvidence, ...]:
    _verify_snapshot_integrity(snapshot)
    evidence: list[SourceBatchEvidence] = []
    for batch_id in snapshot.source_ingestion_batch_ids:
        observations = tuple(
            observation
            for observation in snapshot.observations
            if observation.ingestion_batch_id == batch_id
        )
        timestamps = tuple(
            _required_timestamp(observation.candle.timestamp)
            for observation in observations
        )
        evidence.append(
            SourceBatchEvidence(
                ingestion_batch_id=batch_id,
                source_candle_count=len(observations),
                range_start=timestamps[0],
                range_end=timestamps[-1],
                source_subset_hash=_sha256(
                    {
                        "ingestion_batch_id": str(batch_id),
                        "observations": [
                            _canonical_candle(observation.candle)
                            for observation in observations
                        ],
                    }
                ),
            )
        )
    return tuple(evidence)


def _approved_definitions_by_identifier() -> dict[str, IntradayFeatureDefinition]:
    approved_definitions = (
        TIER_A_FEATURE_DEFINITIONS
        + ATR_FEATURE_DEFINITIONS
        + EMA_FEATURE_DEFINITIONS
        + RSI_FEATURE_DEFINITIONS
    )
    definitions = {
        definition.metadata.identifier: definition
        for definition in approved_definitions
    }
    if len(definitions) != len(approved_definitions):
        raise FeatureComputationError(
            "Approved feature implementations contain duplicate identifiers."
        )
    if set(definitions) != {
        metadata.identifier for metadata in INTRADAY_FEATURE_REGISTRY.definitions
    }:
        raise FeatureComputationError(
            "Approved feature implementations do not match the registry."
        )
    return definitions


def _dependency_inputs(
    metadata: FeatureDefinitionMetadata,
    computed_values: dict[str, tuple[FeatureValue, ...]],
    registry_definitions: tuple[FeatureDefinitionMetadata, ...],
) -> tuple[FeatureDependencyInput, ...]:
    metadata_by_identifier = {
        definition.identifier: definition for definition in registry_definitions
    }
    inputs: list[FeatureDependencyInput] = []
    for contract in metadata.dependency_contracts:
        dependency_metadata = metadata_by_identifier[contract.identifier]
        if dependency_metadata.definition_version != contract.definition_version:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} dependency version mismatch."
            )
        dependency_values = computed_values.get(contract.identifier)
        if dependency_values is None:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} dependency is unavailable."
            )
        for output_name in contract.output_names:
            inputs.append(
                FeatureDependencyInput(
                    definition_identifier=contract.identifier,
                    definition_version=contract.definition_version,
                    output_name=output_name,
                    values=tuple(
                        value
                        for value in dependency_values
                        if value.feature_name == output_name
                    ),
                )
            )
    return tuple(inputs)


def _feature_dependency_memberships(
    metadata: FeatureDefinitionMetadata,
    values: tuple[FeatureValue, ...],
    dependency_lookup: dict[tuple[str, str, str, datetime], PipelineFeatureValue],
) -> tuple[PipelineFeatureDependency, ...]:
    allowed_dependencies = {
        (
            contract.identifier,
            contract.definition_version,
            output_name,
        )
        for contract in metadata.dependency_contracts
        for output_name in contract.output_names
    }
    recursive_outputs = (
        {output.identifier for output in metadata.outputs}
        if metadata.history_type is FeatureHistoryType.RECURSIVE
        else set()
    )
    allowed_dependencies.update(
        (
            metadata.identifier,
            metadata.definition_version,
            output_name,
        )
        for output_name in recursive_outputs
    )
    previous_by_output: dict[tuple[str, datetime], datetime | None] = {}
    for output_name in recursive_outputs:
        previous_timestamp = None
        for value in sorted(
            (value for value in values if value.feature_name == output_name),
            key=lambda value: value.timestamp,
        ):
            previous_by_output[(output_name, value.timestamp)] = previous_timestamp
            previous_timestamp = value.timestamp
    memberships: list[PipelineFeatureDependency] = []
    for value in values:
        if value.dependencies and not allowed_dependencies:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} emitted undeclared dependencies."
            )
        for ordinal, dependency in enumerate(value.dependencies):
            dependency_contract = (
                dependency.definition_identifier,
                dependency.definition_version,
                dependency.output_name,
            )
            if dependency_contract not in allowed_dependencies:
                raise FeatureComputationError(
                    f"Feature {metadata.identifier} emitted an incompatible "
                    "dependency membership."
                )
            if dependency.definition_identifier == metadata.identifier:
                expected_timestamp = previous_by_output.get(
                    (value.feature_name, value.timestamp)
                )
                if (
                    dependency.definition_version != metadata.definition_version
                    or dependency.output_name != value.feature_name
                    or dependency.timestamp != expected_timestamp
                ):
                    raise FeatureComputationError(
                        f"Feature {metadata.identifier} emitted invalid recursive "
                        "predecessor lineage."
                    )
            dependency_value = dependency_lookup.get(
                dependency_contract + (dependency.timestamp,)
            )
            if dependency_value is None:
                raise FeatureComputationError(
                    f"Feature {metadata.identifier} dependency value is missing."
                )
            memberships.append(
                PipelineFeatureDependency(
                    consumer_feature_identifier=metadata.identifier,
                    consumer_definition_version=metadata.definition_version,
                    consumer_output_name=value.feature_name,
                    consumer_candle_timestamp=value.timestamp,
                    dependency_ordinal=ordinal,
                    dependency_feature_identifier=(dependency_value.feature_identifier),
                    dependency_definition_version=(dependency_value.definition_version),
                    dependency_output_name=dependency_value.output_name,
                    dependency_candle_timestamp=(dependency_value.candle_timestamp),
                    dependency_available_at=dependency_value.available_at,
                    dependency_value=dependency_value.value,
                )
            )
        recursive_memberships = tuple(
            dependency
            for dependency in value.dependencies
            if dependency.definition_identifier == metadata.identifier
        )
        expected_predecessor = previous_by_output.get(
            (value.feature_name, value.timestamp)
        )
        if expected_predecessor is None and recursive_memberships:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} initialization emitted a "
                "recursive predecessor."
            )
        if expected_predecessor is not None and len(recursive_memberships) != 1:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} omitted its recursive predecessor."
            )
    return tuple(memberships)


def _validate_feature_output(
    metadata: FeatureDefinitionMetadata,
    values: tuple[FeatureValue, ...],
    snapshot: IntradaySourceSnapshot,
) -> None:
    actual: dict[tuple[datetime, str], FeatureValue] = {}
    for value in values:
        identity = (value.timestamp, value.feature_name)
        if identity in actual:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} emitted a duplicate output."
            )
        if value.feature_name not in {output.identifier for output in metadata.outputs}:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} emitted an undeclared output."
            )
        if not isinstance(value.value, Decimal) or not value.value.is_finite():
            raise FeatureComputationError(
                f"Feature {metadata.identifier} emitted an invalid Decimal."
            )
        if quantize_feature_value(value.value) != value.value:
            raise FeatureComputationError(
                f"Feature {metadata.identifier} violated Decimal precision."
            )
        actual[identity] = value

    expected = {
        (observation.candle.timestamp, output.identifier)
        for output in metadata.outputs
        for index, observation in enumerate(snapshot.observations)
        if index >= output.minimum_observations - 1
    }
    if set(actual) != expected:
        missing = expected - set(actual)
        unexpected = set(actual) - expected
        raise FeatureComputationError(
            f"Feature {metadata.identifier} violated warm-up or coverage: "
            f"missing={len(missing)}, unexpected={len(unexpected)}."
        )


def _verify_prefix_invariance(
    definition: IntradayFeatureDefinition,
    full_values: tuple[FeatureValue, ...],
    snapshot: IntradaySourceSnapshot,
    dependency_inputs: tuple[FeatureDependencyInput, ...],
) -> None:
    for prefix_length in range(1, len(snapshot.observations) + 1):
        prefix = snapshot.candles[:prefix_length]
        prefix_end = _required_timestamp(prefix[-1].timestamp)
        prefix_dependencies = tuple(
            FeatureDependencyInput(
                definition_identifier=value.definition_identifier,
                definition_version=value.definition_version,
                output_name=value.output_name,
                values=tuple(
                    dependency_value
                    for dependency_value in value.values
                    if dependency_value.timestamp <= prefix_end
                ),
            )
            for value in dependency_inputs
        )
        prefix_values = definition.compute(
            prefix,
            snapshot.timeframe,
            prefix_dependencies,
        )
        expected = tuple(
            value for value in full_values if value.timestamp <= prefix_end
        )
        if prefix_values != expected:
            raise FeatureComputationError(
                f"Feature {definition.metadata.identifier} failed prefix "
                f"invariance at observation {prefix_length}."
            )


def _validate_pipeline_values(
    values: tuple[PipelineFeatureValue, ...],
    snapshot: IntradaySourceSnapshot,
) -> None:
    seen: set[tuple[datetime, str]] = set()
    previous_sort_key: tuple[datetime, int] | None = None
    output_order = {
        name: index for index, name in enumerate(INTRADAY_FEATURE_REGISTRY.output_names)
    }
    source_timestamps = {
        _required_timestamp(observation.candle.timestamp)
        for observation in snapshot.observations
    }
    for value in values:
        identity = (value.candle_timestamp, value.output_name)
        if identity in seen:
            raise FeatureComputationError(
                "Pipeline emitted a duplicate feature identity."
            )
        if value.candle_timestamp not in source_timestamps:
            raise FeatureComputationError("Pipeline emitted a non-source timestamp.")
        expected_available_at = feature_available_at(
            value.candle_timestamp,
            snapshot.timeframe,
            FeatureAvailabilityRule.CANDLE_CLOSE,
        )
        if value.available_at != expected_available_at:
            raise FeatureComputationError(
                "Pipeline emitted an invalid availability timestamp."
            )
        sort_key = (
            value.candle_timestamp,
            output_order[value.output_name],
        )
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            raise FeatureComputationError(
                "Pipeline output is not deterministically ordered."
            )
        seen.add(identity)
        previous_sort_key = sort_key


def _validate_pipeline_dependencies(
    dependencies: tuple[PipelineFeatureDependency, ...],
    values: tuple[PipelineFeatureValue, ...],
) -> None:
    values_by_identity = {
        (
            value.feature_identifier,
            value.definition_version,
            value.output_name,
            value.candle_timestamp,
        ): value
        for value in values
    }
    ordinals_by_consumer: dict[tuple[str, str, str, datetime], list[int]] = {}
    seen: set[tuple[str, str, str, datetime, int]] = set()
    for membership in dependencies:
        consumer_identity = (
            membership.consumer_feature_identifier,
            membership.consumer_definition_version,
            membership.consumer_output_name,
            membership.consumer_candle_timestamp,
        )
        membership_identity = consumer_identity + (membership.dependency_ordinal,)
        if membership_identity in seen:
            raise FeatureComputationError(
                "Pipeline emitted a duplicate dependency membership."
            )
        consumer = values_by_identity.get(consumer_identity)
        dependency = values_by_identity.get(
            (
                membership.dependency_feature_identifier,
                membership.dependency_definition_version,
                membership.dependency_output_name,
                membership.dependency_candle_timestamp,
            )
        )
        if consumer is None or dependency is None:
            raise FeatureComputationError(
                "Pipeline dependency membership references a missing value."
            )
        if (
            membership.dependency_available_at != dependency.available_at
            or membership.dependency_value != dependency.value
            or dependency.available_at > consumer.available_at
        ):
            raise FeatureComputationError(
                "Pipeline dependency membership failed point-in-time validation."
            )
        seen.add(membership_identity)
        ordinals_by_consumer.setdefault(consumer_identity, []).append(
            membership.dependency_ordinal
        )
    for ordinals in ordinals_by_consumer.values():
        if ordinals != list(range(len(ordinals))):
            raise FeatureComputationError(
                "Pipeline dependency memberships are not canonically ordered."
            )


def _verify_snapshot_integrity(snapshot: IntradaySourceSnapshot) -> None:
    rebuilt = build_intraday_source_snapshot(
        asset_identifier=snapshot.asset_identifier,
        quote_currency=snapshot.quote_currency,
        timeframe=snapshot.timeframe,
        observations=snapshot.observations,
    )
    if rebuilt != snapshot:
        raise FeatureComputationError(
            "Source snapshot metadata or hashes failed integrity verification."
        )


def _validate_source_observations(
    observations: tuple[SourceCandleObservation, ...],
    timeframe: CandleTimeframe,
) -> None:
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise FeatureComputationError(
            "Intraday snapshots support only 5m, 10m, and 15m."
        )
    if not observations:
        raise FeatureComputationError(
            "Intraday source snapshot requires candle observations."
        )

    expected_step = timeframe_duration(timeframe)
    previous_timestamp: datetime | None = None
    for observation in observations:
        if not observation.is_complete:
            raise FeatureComputationError(
                "Incomplete candles cannot enter a feature snapshot."
            )
        if not isinstance(observation.ingestion_batch_id, UUID):
            raise FeatureComputationError(
                "Source observation requires an ingestion batch UUID."
            )
        candle = observation.candle
        timestamp = candle.timestamp
        if timestamp is None:
            raise FeatureComputationError(
                "Source observation is missing its timestamp."
            )
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise FeatureComputationError("Source timestamp must be timezone-aware.")
        if timestamp.utcoffset() != timedelta(0):
            raise FeatureComputationError("Source timestamp must be canonical UTC.")
        if floor_timeframe_boundary(timestamp, timeframe) != timestamp:
            raise FeatureComputationError("Source timestamp is not timeframe-aligned.")
        if (
            previous_timestamp is not None
            and timestamp - previous_timestamp != expected_step
        ):
            raise FeatureComputationError(
                "Source observations must be consecutive and chronological."
            )
        _validate_source_values(candle)
        previous_timestamp = timestamp


def _validate_source_values(candle: Candle) -> None:
    values = (
        candle.open,
        candle.high,
        candle.low,
        candle.close,
        candle.volume,
    )
    if any(not isinstance(value, Decimal) for value in values):
        raise FeatureComputationError(
            "Source observation contains a missing or non-Decimal value."
        )
    open_price = _required_decimal(candle.open)
    high = _required_decimal(candle.high)
    low = _required_decimal(candle.low)
    close = _required_decimal(candle.close)
    volume = _required_decimal(candle.volume)
    if any(not value.is_finite() for value in (open_price, high, low, close, volume)):
        raise FeatureComputationError("Source observation contains a non-finite value.")
    if min(open_price, high, low, close) <= 0 or volume < 0:
        raise FeatureComputationError(
            "Source observation contains an invalid price or volume."
        )
    if low > high or not low <= open_price <= high or not low <= close <= high:
        raise FeatureComputationError(
            "Source observation contains an invalid OHLC relationship."
        )


def _snapshot_data_hash(
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
    observations: tuple[SourceCandleObservation, ...],
) -> str:
    payload = {
        "asset_identifier": asset_identifier,
        "quote_currency": quote_currency,
        "timeframe": timeframe.value,
        "candles": [
            _canonical_candle(observation.candle) for observation in observations
        ],
    }
    return _sha256(payload)


def _snapshot_provenance_hash(
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
    observations: tuple[SourceCandleObservation, ...],
) -> str:
    payload = {
        "asset_identifier": asset_identifier,
        "quote_currency": quote_currency,
        "timeframe": timeframe.value,
        "observations": [
            {
                "candle": _canonical_candle(observation.candle),
                "ingestion_batch_id": str(observation.ingestion_batch_id),
                "is_complete": observation.is_complete,
            }
            for observation in observations
        ],
    }
    return _sha256(payload)


def _pipeline_result_hash(
    *,
    snapshot: IntradaySourceSnapshot,
    execution_order: tuple[str, ...],
    values: tuple[PipelineFeatureValue, ...],
    dependency_memberships: tuple[PipelineFeatureDependency, ...],
) -> str:
    payload = {
        "pipeline_version": INTRADAY_PIPELINE_VERSION,
        "source_data_hash": snapshot.data_hash,
        "source_provenance_hash": snapshot.provenance_hash,
        "registry_hash": INTRADAY_FEATURE_REGISTRY.configuration_hash,
        "registry_schema_version": INTRADAY_FEATURE_REGISTRY.schema_version,
        "availability_contract_version": (FEATURE_AVAILABILITY_CONTRACT_VERSION),
        "execution_order": list(execution_order),
        "values": [
            {
                "feature_identifier": value.feature_identifier,
                "definition_version": value.definition_version,
                "output_name": value.output_name,
                "candle_timestamp": _canonical_timestamp(value.candle_timestamp),
                "available_at": _canonical_timestamp(value.available_at),
                "value": _canonical_decimal(value.value),
            }
            for value in values
        ],
        "dependency_memberships": [
            {
                "consumer_feature_identifier": (membership.consumer_feature_identifier),
                "consumer_definition_version": (membership.consumer_definition_version),
                "consumer_output_name": membership.consumer_output_name,
                "consumer_candle_timestamp": _canonical_timestamp(
                    membership.consumer_candle_timestamp
                ),
                "dependency_ordinal": membership.dependency_ordinal,
                "dependency_feature_identifier": (
                    membership.dependency_feature_identifier
                ),
                "dependency_definition_version": (
                    membership.dependency_definition_version
                ),
                "dependency_output_name": membership.dependency_output_name,
                "dependency_candle_timestamp": _canonical_timestamp(
                    membership.dependency_candle_timestamp
                ),
                "dependency_available_at": _canonical_timestamp(
                    membership.dependency_available_at
                ),
                "dependency_value": _canonical_decimal(membership.dependency_value),
            }
            for membership in dependency_memberships
        ],
    }
    return _sha256(payload)


def _canonical_candle(candle: Candle) -> dict[str, str]:
    return {
        "timestamp": _canonical_timestamp(_required_timestamp(candle.timestamp)),
        "open": _canonical_decimal(_required_decimal(candle.open)),
        "high": _canonical_decimal(_required_decimal(candle.high)),
        "low": _canonical_decimal(_required_decimal(candle.low)),
        "close": _canonical_decimal(_required_decimal(candle.close)),
        "volume": _canonical_decimal(_required_decimal(candle.volume)),
    }


def _canonical_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical_decimal(value: Decimal) -> str:
    return format(value, "f")


def _sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("Source timestamp is unexpectedly missing.")
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise FeatureComputationError("Source value is unexpectedly missing.")
    return value
