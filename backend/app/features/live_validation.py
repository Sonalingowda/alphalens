"""Live end-to-end validation for the approved intraday feature pipeline."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.features.contracts import FeatureComputationError
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    IntradayFeaturePipelineResult,
    run_intraday_feature_pipeline,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import CandleTimeframe
from app.market_data.provider import MarketDataProvider
from app.persistence.intraday import (
    IntradayIngestionItem,
    ingest_btc_usd_intraday,
)
from app.persistence.intraday_features import (
    count_active_intraday_feature_runs,
    count_intraday_feature_values,
    get_stored_intraday_feature_run_evidence,
    load_intraday_source_snapshot,
    persist_intraday_feature_result,
    StoredIntradayFeatureRunEvidence,
)


_VALIDATION_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class LiveIntradayFeatureValidation:
    timeframe: CandleTimeframe
    ingestion_batch_id: UUID
    source_candle_count: int
    excluded_incomplete_candle_count: int
    feature_value_count: int
    first_run_id: UUID
    second_run_id: UUID
    first_inserted_value_count: int
    second_inserted_value_count: int
    second_reused_value_count: int
    canonical_value_count: int
    source_membership_count: int
    value_membership_count: int
    pipeline_version: str
    registry_hash: str
    source_data_hash: str
    source_provenance_hash: str
    result_hash: str
    deterministic: bool
    active_run_verified: bool
    incomplete_candles_processed: int


@dataclass(frozen=True, slots=True)
class LiveIntradayFeatureValidationReport:
    provider: str
    asset_identifier: str
    quote_currency: str
    pipeline_version: str
    registry_hash: str
    validations: tuple[LiveIntradayFeatureValidation, ...]


async def validate_live_intraday_feature_pipeline(
    provider: MarketDataProvider,
    session_maker: async_sessionmaker[AsyncSession],
) -> LiveIntradayFeatureValidationReport:
    ingestion = await ingest_btc_usd_intraday(provider, session_maker)
    items_by_timeframe = {
        item.sample.timeframe: item for item in ingestion.items
    }
    if set(items_by_timeframe) != set(_VALIDATION_TIMEFRAMES):
        raise FeatureComputationError(
            "Live ingestion did not return the complete approved timeframe set."
        )

    validations = []
    for timeframe in _VALIDATION_TIMEFRAMES:
        item = items_by_timeframe[timeframe]
        _verify_ingestion_item(item)
        validations.append(
            await _validate_timeframe(
                session_maker,
                item,
            )
        )

    return LiveIntradayFeatureValidationReport(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        pipeline_version=INTRADAY_PIPELINE_VERSION,
        registry_hash=INTRADAY_FEATURE_REGISTRY.configuration_hash,
        validations=tuple(validations),
    )


async def _validate_timeframe(
    session_maker: async_sessionmaker[AsyncSession],
    item: IntradayIngestionItem,
) -> LiveIntradayFeatureValidation:
    timeframe = item.sample.timeframe
    async with session_maker() as session:
        snapshot = await load_intraday_source_snapshot(
            session,
            timeframe,
        )
        value_count_before = await count_intraday_feature_values(
            session,
            timeframe,
        )

    first_result = run_intraday_feature_pipeline(snapshot)
    repeated_result = run_intraday_feature_pipeline(snapshot)
    if first_result != repeated_result:
        raise FeatureComputationError(
            f"{timeframe.value} pipeline execution is not deterministic."
        )
    if first_result.pipeline_version != INTRADAY_PIPELINE_VERSION:
        raise FeatureComputationError(
            f"{timeframe.value} pipeline version verification failed."
        )
    if (
        first_result.registry_hash
        != INTRADAY_FEATURE_REGISTRY.configuration_hash
    ):
        raise FeatureComputationError(
            f"{timeframe.value} registry hash verification failed."
        )
    if any(not observation.is_complete for observation in snapshot.observations):
        raise FeatureComputationError(
            f"{timeframe.value} snapshot contains an incomplete candle."
        )

    expected_inserted_count = (
        len(first_result.values) - value_count_before
    )
    if expected_inserted_count < 0:
        raise FeatureComputationError(
            f"{timeframe.value} stored feature count exceeds pipeline output."
        )

    async with session_maker() as session:
        first_persistence = await persist_intraday_feature_result(
            session,
            snapshot,
            first_result,
        )
    async with session_maker() as session:
        second_persistence = await persist_intraday_feature_result(
            session,
            snapshot,
            repeated_result,
        )
    if first_persistence.inserted_value_count != expected_inserted_count:
        raise FeatureComputationError(
            f"{timeframe.value} first-run insertion count is inconsistent."
        )
    if (
        second_persistence.inserted_value_count != 0
        or second_persistence.reused_value_count
        != len(first_result.values)
    ):
        raise FeatureComputationError(
            f"{timeframe.value} repeated persistence is not idempotent."
        )

    async with session_maker() as session:
        first_evidence = await get_stored_intraday_feature_run_evidence(
            session,
            first_persistence.feature_run_id,
        )
        second_evidence = await get_stored_intraday_feature_run_evidence(
            session,
            second_persistence.feature_run_id,
        )
        active_run_count = await count_active_intraday_feature_runs(
            session,
            timeframe,
        )

    if second_evidence.canonical_value_count != len(first_result.values):
        raise FeatureComputationError(
            f"{timeframe.value} canonical feature coverage is incomplete."
        )
    _verify_hash_evidence(first_result, first_evidence)
    _verify_hash_evidence(first_result, second_evidence)
    if (
        first_evidence.is_active
        or not second_evidence.is_active
        or active_run_count != 1
    ):
        raise FeatureComputationError(
            f"{timeframe.value} active-run verification failed."
        )
    if (
        second_evidence.source_membership_count
        != len(snapshot.source_ingestion_batch_ids)
        or second_evidence.value_membership_count
        != len(first_result.values)
    ):
        raise FeatureComputationError(
            f"{timeframe.value} persisted memberships are incomplete."
        )

    return LiveIntradayFeatureValidation(
        timeframe=timeframe,
        ingestion_batch_id=item.persistence.ingestion_batch_id,
        source_candle_count=len(snapshot.observations),
        excluded_incomplete_candle_count=(
            item.sample.excluded_incomplete_candle_count
        ),
        feature_value_count=len(first_result.values),
        first_run_id=first_persistence.feature_run_id,
        second_run_id=second_persistence.feature_run_id,
        first_inserted_value_count=(
            first_persistence.inserted_value_count
        ),
        second_inserted_value_count=(
            second_persistence.inserted_value_count
        ),
        second_reused_value_count=(
            second_persistence.reused_value_count
        ),
        canonical_value_count=second_evidence.canonical_value_count,
        source_membership_count=(
            second_evidence.source_membership_count
        ),
        value_membership_count=second_evidence.value_membership_count,
        pipeline_version=first_result.pipeline_version,
        registry_hash=first_result.registry_hash,
        source_data_hash=first_result.source_data_hash,
        source_provenance_hash=first_result.source_provenance_hash,
        result_hash=first_result.result_hash,
        deterministic=True,
        active_run_verified=True,
        incomplete_candles_processed=0,
    )


def _verify_ingestion_item(item: IntradayIngestionItem) -> None:
    if not item.persistence.validation_passed:
        raise FeatureComputationError(
            f"{item.sample.timeframe.value} live ingestion failed validation."
        )
    if not item.sample.candles:
        raise FeatureComputationError(
            f"{item.sample.timeframe.value} live ingestion returned no candles."
        )
    if any(
        candle.timestamp is None
        or candle.timestamp >= item.sample.requested_end_exclusive
        for candle in item.sample.candles
    ):
        raise FeatureComputationError(
            f"{item.sample.timeframe.value} ingestion retained an incomplete candle."
        )


def _verify_hash_evidence(
    result: IntradayFeaturePipelineResult,
    evidence: StoredIntradayFeatureRunEvidence,
) -> None:
    expected = (
        INTRADAY_PIPELINE_VERSION,
        result.source_data_hash,
        result.source_provenance_hash,
        result.registry_hash,
        result.result_hash,
        len(result.values),
    )
    actual = (
        evidence.pipeline_version,
        evidence.source_data_hash,
        evidence.source_provenance_hash,
        evidence.registry_hash,
        evidence.result_hash,
        evidence.persisted_value_count,
    )
    if actual != expected:
        raise FeatureComputationError(
            "Persisted feature run hash or count verification failed."
        )
