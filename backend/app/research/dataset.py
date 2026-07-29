"""Deterministic model-ready dataset construction."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    CandleRecord,
    EngineeredFeatureRecord,
    FeaturePipelineRunRecord,
    ForwardLogReturnTargetRecord,
    ForwardLogReturnTargetRunRecord,
    IngestionBatchRecord,
    ValidationRunRecord,
)


MODEL_FEATURE_NAMES: tuple[str, ...] = (
    "bollinger_20_2_lower",
    "bollinger_20_2_middle",
    "bollinger_20_2_upper",
    "ema_20",
    "ema_50",
    "macd_12_26_9_histogram",
    "macd_12_26_9_line",
    "macd_12_26_9_signal",
    "rsi_14",
    "sma_20",
    "sma_50",
    "volume_sma_20",
)


class ResearchDatasetError(ValueError):
    """Raised when synchronized model-ready evidence is unavailable."""


@dataclass(frozen=True, slots=True)
class ModelObservation:
    prediction_timestamp: datetime
    label_available_at: datetime
    feature_values: tuple[Decimal, ...]
    target_value: Decimal


@dataclass(frozen=True, slots=True)
class ResearchSplit:
    sequence: int
    train_start: datetime
    train_end: datetime
    purge_start: datetime
    purge_end: datetime
    test_start: datetime
    test_end: datetime


@dataclass(frozen=True, slots=True)
class ModelReadyDataset:
    asset_identifier: str
    quote_currency: str
    timeframe: str
    source_ingestion_batch_id: UUID
    source_feature_run_id: UUID
    source_target_run_id: UUID
    validation_run_id: UUID
    source_dataset_hash: str
    model_dataset_hash: str
    feature_pipeline_version: str
    target_name: str
    target_version: str
    target_definition_hash: str
    validation_split_hash: str
    feature_names: tuple[str, ...]
    source_observation_count: int
    total_eligible_observation_count: int
    development_eligible_observation_count: int
    holdout_eligible_observation_count: int
    excluded_feature_warmup_count: int
    excluded_missing_target_count: int
    development_range_start: datetime
    development_range_end: datetime
    final_holdout_start: datetime
    final_holdout_end: datetime
    development_observations: tuple[ModelObservation, ...]
    validation_splits: tuple[ResearchSplit, ...]
    point_in_time_validated: bool


async def build_model_ready_dataset(
    session: AsyncSession,
) -> ModelReadyDataset:
    provenance = await _load_active_provenance(session)
    (
        source_batch,
        feature_run,
        target_run,
        validation_run,
    ) = provenance
    _validate_provenance(*provenance)

    candle_timestamps = tuple(
        (
            await session.scalars(
                select(CandleRecord.candle_timestamp)
                .where(
                    CandleRecord.asset_identifier == "BTC",
                    CandleRecord.quote_currency == "USD",
                    CandleRecord.timeframe == "1d",
                    CandleRecord.is_complete.is_(True),
                )
                .order_by(CandleRecord.candle_timestamp)
            )
        ).all()
    )
    if len(candle_timestamps) != source_batch.candle_count:
        raise ResearchDatasetError(
            "The active candle batch count does not match persisted candles."
        )

    complete_feature_timestamps = frozenset(
        row[0]
        for row in (
            await session.execute(
                select(EngineeredFeatureRecord.candle_timestamp)
                .where(
                    EngineeredFeatureRecord.computation_run_id
                    == feature_run.id,
                )
                .group_by(EngineeredFeatureRecord.candle_timestamp)
                .having(
                    func.count(EngineeredFeatureRecord.id)
                    == len(MODEL_FEATURE_NAMES)
                )
            )
        ).all()
    )
    target_timestamps = frozenset(
        (
            await session.scalars(
                select(
                    ForwardLogReturnTargetRecord.prediction_timestamp
                ).where(
                    ForwardLogReturnTargetRecord.generation_run_id
                    == target_run.id,
                )
            )
        ).all()
    )
    all_eligible_timestamps = (
        complete_feature_timestamps & target_timestamps
    )
    development_eligible_timestamps = frozenset(
        timestamp
        for timestamp in all_eligible_timestamps
        if timestamp <= validation_run.development_range_end
    )
    holdout_eligible_timestamps = frozenset(
        timestamp
        for timestamp in all_eligible_timestamps
        if validation_run.final_holdout_start
        <= timestamp
        <= validation_run.final_holdout_end
    )
    if all_eligible_timestamps != (
        development_eligible_timestamps | holdout_eligible_timestamps
    ):
        raise ResearchDatasetError(
            "Eligible observations fall outside development and holdout "
            "boundaries."
        )

    feature_rows = (
        await session.execute(
            select(
                EngineeredFeatureRecord.candle_timestamp,
                EngineeredFeatureRecord.feature_name,
                EngineeredFeatureRecord.feature_value,
            )
            .where(
                EngineeredFeatureRecord.computation_run_id == feature_run.id,
                EngineeredFeatureRecord.candle_timestamp
                <= validation_run.development_range_end,
            )
            .order_by(
                EngineeredFeatureRecord.candle_timestamp,
                EngineeredFeatureRecord.feature_name,
            )
        )
    ).all()
    target_rows = (
        await session.scalars(
            select(ForwardLogReturnTargetRecord)
            .where(
                ForwardLogReturnTargetRecord.generation_run_id
                == target_run.id,
                ForwardLogReturnTargetRecord.prediction_timestamp
                <= validation_run.development_range_end,
            )
            .order_by(
                ForwardLogReturnTargetRecord.prediction_timestamp
            )
        )
    ).all()

    feature_values: dict[datetime, dict[str, Decimal]] = {}
    for timestamp, feature_name, feature_value in feature_rows:
        feature_values.setdefault(timestamp, {})[feature_name] = feature_value
    targets = {
        target.prediction_timestamp: target for target in target_rows
    }

    observations: list[ModelObservation] = []
    for timestamp in sorted(development_eligible_timestamps):
        values_by_name = feature_values.get(timestamp)
        target = targets.get(timestamp)
        if values_by_name is None or target is None:
            raise ResearchDatasetError(
                "An eligible development observation is incomplete."
            )
        if tuple(sorted(values_by_name)) != MODEL_FEATURE_NAMES:
            raise ResearchDatasetError(
                f"Feature vector at {timestamp.isoformat()} does not match "
                "the approved feature set."
            )
        if (
            target.source_ingestion_batch_id != source_batch.id
            or target.source_feature_run_id != feature_run.id
            or target.feature_pipeline_version
            != feature_run.pipeline_version
            or target.dataset_hash != feature_run.source_data_hash
        ):
            raise ResearchDatasetError(
                "A target row does not match active dataset provenance."
            )
        if target.label_available_at <= timestamp:
            raise ResearchDatasetError(
                "A target label is not strictly forward-looking."
            )
        observations.append(
            ModelObservation(
                prediction_timestamp=timestamp,
                label_available_at=target.label_available_at,
                feature_values=tuple(
                    values_by_name[name] for name in MODEL_FEATURE_NAMES
                ),
                target_value=target.target_value,
            )
        )

    ordered_observations = tuple(observations)
    model_dataset_hash = _model_dataset_hash(ordered_observations)
    splits = tuple(
        _parse_split(boundary)
        for boundary in validation_run.split_boundaries
    )
    if tuple(split.sequence for split in splits) != tuple(
        range(1, validation_run.split_count + 1)
    ):
        raise ResearchDatasetError(
            "Validation split sequences are incomplete or unordered."
        )

    return ModelReadyDataset(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        source_ingestion_batch_id=source_batch.id,
        source_feature_run_id=feature_run.id,
        source_target_run_id=target_run.id,
        validation_run_id=validation_run.id,
        source_dataset_hash=feature_run.source_data_hash,
        model_dataset_hash=model_dataset_hash,
        feature_pipeline_version=feature_run.pipeline_version,
        target_name=target_run.target_name,
        target_version=target_run.target_version,
        target_definition_hash=target_run.target_definition_hash,
        validation_split_hash=validation_run.split_hash,
        feature_names=MODEL_FEATURE_NAMES,
        source_observation_count=len(candle_timestamps),
        total_eligible_observation_count=len(all_eligible_timestamps),
        development_eligible_observation_count=len(
            development_eligible_timestamps
        ),
        holdout_eligible_observation_count=len(
            holdout_eligible_timestamps
        ),
        excluded_feature_warmup_count=(
            len(candle_timestamps) - len(complete_feature_timestamps)
        ),
        excluded_missing_target_count=(
            len(candle_timestamps) - len(target_timestamps)
        ),
        development_range_start=validation_run.development_range_start,
        development_range_end=validation_run.development_range_end,
        final_holdout_start=validation_run.final_holdout_start,
        final_holdout_end=validation_run.final_holdout_end,
        development_observations=ordered_observations,
        validation_splits=splits,
        point_in_time_validated=True,
    )


async def _load_active_provenance(
    session: AsyncSession,
) -> tuple[
    IngestionBatchRecord,
    FeaturePipelineRunRecord,
    ForwardLogReturnTargetRunRecord,
    ValidationRunRecord,
]:
    source_batch = (
        await session.scalars(
            select(IngestionBatchRecord).where(
                IngestionBatchRecord.asset_identifier == "BTC",
                IngestionBatchRecord.quote_currency == "USD",
                IngestionBatchRecord.timeframe == "1d",
                IngestionBatchRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    feature_run = (
        await session.scalars(
            select(FeaturePipelineRunRecord).where(
                FeaturePipelineRunRecord.asset_identifier == "BTC",
                FeaturePipelineRunRecord.quote_currency == "USD",
                FeaturePipelineRunRecord.timeframe == "1d",
                FeaturePipelineRunRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    target_run = (
        await session.scalars(
            select(ForwardLogReturnTargetRunRecord).where(
                ForwardLogReturnTargetRunRecord.asset_identifier == "BTC",
                ForwardLogReturnTargetRunRecord.quote_currency == "USD",
                ForwardLogReturnTargetRunRecord.timeframe == "1d",
                ForwardLogReturnTargetRunRecord.target_name
                == "forward_log_return",
                ForwardLogReturnTargetRunRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    validation_run = (
        await session.scalars(
            select(ValidationRunRecord).where(
                ValidationRunRecord.asset_identifier == "BTC",
                ValidationRunRecord.quote_currency == "USD",
                ValidationRunRecord.timeframe == "1d",
                ValidationRunRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    if any(
        record is None
        for record in (
            source_batch,
            feature_run,
            target_run,
            validation_run,
        )
    ):
        raise ResearchDatasetError(
            "Active candle, feature, target, and validation provenance is "
            "required."
        )
    return source_batch, feature_run, target_run, validation_run


def _validate_provenance(
    source_batch: IngestionBatchRecord,
    feature_run: FeaturePipelineRunRecord,
    target_run: ForwardLogReturnTargetRunRecord,
    validation_run: ValidationRunRecord,
) -> None:
    if not source_batch.validation_passed:
        raise ResearchDatasetError("The active candle batch is invalid.")
    if not feature_run.point_in_time_validated:
        raise ResearchDatasetError("The active feature run is invalid.")
    if not target_run.point_in_time_validated:
        raise ResearchDatasetError("The active target run is invalid.")
    if (
        feature_run.source_ingestion_batch_id != source_batch.id
        or target_run.source_ingestion_batch_id != source_batch.id
        or validation_run.source_ingestion_batch_id != source_batch.id
        or target_run.source_feature_run_id != feature_run.id
        or validation_run.source_feature_run_id != feature_run.id
        or target_run.feature_pipeline_version
        != feature_run.pipeline_version
        or validation_run.feature_pipeline_version
        != feature_run.pipeline_version
        or target_run.dataset_hash != feature_run.source_data_hash
        or validation_run.source_data_hash != feature_run.source_data_hash
    ):
        raise ResearchDatasetError(
            "Active provenance records do not describe one synchronized "
            "research dataset."
        )
    if target_run.target_version != "1.0.0" or target_run.horizon != 5:
        raise ResearchDatasetError(
            "The active target does not match the approved definition."
        )
    if not validation_run.holdout_excluded:
        raise ResearchDatasetError("The final holdout is not isolated.")


def _parse_split(boundary: dict[str, object]) -> ResearchSplit:
    try:
        train = boundary["train"]
        purge = boundary["purge_gap"]
        test = boundary["test"]
        if not all(
            isinstance(value, dict) for value in (train, purge, test)
        ):
            raise TypeError
        return ResearchSplit(
            sequence=int(boundary["sequence"]),
            train_start=datetime.fromisoformat(str(train["start"])),
            train_end=datetime.fromisoformat(str(train["end"])),
            purge_start=datetime.fromisoformat(str(purge["start"])),
            purge_end=datetime.fromisoformat(str(purge["end"])),
            test_start=datetime.fromisoformat(str(test["start"])),
            test_end=datetime.fromisoformat(str(test["end"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ResearchDatasetError(
            "A persisted validation split boundary is malformed."
        ) from exc


def _model_dataset_hash(
    observations: tuple[ModelObservation, ...],
) -> str:
    digest = sha256()
    digest.update(("|".join(MODEL_FEATURE_NAMES) + "\n").encode())
    for observation in observations:
        fields = (
            observation.prediction_timestamp.isoformat(),
            observation.label_available_at.isoformat(),
            *(format(value, "f") for value in observation.feature_values),
            format(observation.target_value, "f"),
        )
        digest.update(("|".join(fields) + "\n").encode())
    return digest.hexdigest()
