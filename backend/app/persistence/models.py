"""SQLAlchemy persistence models."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IngestionBatchRecord(Base):
    __tablename__ = "market_data_ingestion_batches"
    __table_args__ = (
        CheckConstraint(
            "requested_start < requested_end_exclusive",
            name="ck_ingestion_batches_valid_range",
        ),
        CheckConstraint(
            "candle_count >= 0 AND persisted_candle_count >= 0",
            name="ck_ingestion_batches_non_negative_counts",
        ),
        CheckConstraint(
            (
                "provider_page_count > 0 "
                "AND excluded_incomplete_candle_count >= 0 "
                "AND excluded_pagination_overlap_count >= 0 "
                "AND provider_page_limit > 0"
            ),
            name="ck_ingestion_batches_valid_pagination_counts",
        ),
        CheckConstraint(
            "insertion_mode IN ('upsert', 'insert_only')",
            name="ck_ingestion_batches_insertion_mode",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    requested_end_exclusive: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    persisted_candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )
    excluded_incomplete_candle_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    excluded_pagination_overlap_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    provider_page_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="720",
    )
    provider_limit_reached: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    pagination_exhausted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    available_range_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    available_range_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    insertion_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="upsert",
    )
    progress_events: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CandleRecord(Base):
    __tablename__ = "market_data_candles"
    __table_args__ = (
        UniqueConstraint(
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "candle_timestamp",
            name="uq_market_candles_asset_quote_timeframe_timestamp",
        ),
        CheckConstraint(
            (
                "open_price > 0 AND high_price > 0 AND low_price > 0 "
                "AND close_price > 0 AND volume >= 0"
            ),
            name="ck_market_candles_positive_values",
        ),
        CheckConstraint(
            (
                "low_price <= high_price "
                "AND open_price BETWEEN low_price AND high_price "
                "AND close_price BETWEEN low_price AND high_price"
            ),
            name="ck_market_candles_ohlc_relationships",
        ),
        CheckConstraint(
            (
                "timeframe <> '1d' OR candle_timestamp = "
                "(date_trunc('day', candle_timestamp AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC')"
            ),
            name="ck_market_candles_daily_utc_alignment",
        ),
        Index("ix_market_candles_ingestion_batch_id", "ingestion_batch_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    candle_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    open_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class FeaturePipelineRunRecord(Base):
    __tablename__ = "feature_pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "source_range_start <= source_range_end",
            name="ck_feature_pipeline_runs_valid_source_range",
        ),
        CheckConstraint(
            (
                "source_candle_count > 0 AND feature_value_count >= 0 "
                "AND persisted_value_count >= 0 "
                "AND persisted_value_count <= feature_value_count"
            ),
            name="ck_feature_pipeline_runs_valid_counts",
        ),
        CheckConstraint(
            "char_length(source_data_hash) = 64",
            name="ck_feature_pipeline_runs_sha256_length",
        ),
        CheckConstraint(
            "point_in_time_validated",
            name="ck_feature_pipeline_runs_point_in_time_validated",
        ),
        Index(
            "ix_feature_pipeline_runs_source_ingestion_batch_id",
            "source_ingestion_batch_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_range_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source_range_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source_data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    feature_value_count: Mapped[int] = mapped_column(Integer, nullable=False)
    persisted_value_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EngineeredFeatureRecord(Base):
    __tablename__ = "engineered_features"
    __table_args__ = (
        UniqueConstraint(
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "candle_timestamp",
            "feature_name",
            "pipeline_version",
            name="uq_engineered_features_identity",
        ),
        CheckConstraint(
            (
                "timeframe <> '1d' OR candle_timestamp = "
                "(date_trunc('day', candle_timestamp AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC')"
            ),
            name="ck_engineered_features_daily_utc_alignment",
        ),
        Index(
            "ix_engineered_features_computation_run_id",
            "computation_run_id",
        ),
        Index(
            "ix_engineered_features_source_ingestion_batch_id",
            "source_ingestion_batch_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    candle_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    feature_name: Mapped[str] = mapped_column(String(96), nullable=False)
    feature_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    computation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feature_pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ValidationRunRecord(Base):
    __tablename__ = "validation_runs"
    __table_args__ = (
        CheckConstraint(
            (
                "minimum_train_size > 0 AND test_size > 0 "
                "AND step_size >= test_size AND final_holdout_size > 0"
            ),
            name="ck_validation_runs_positive_window_sizes",
        ),
        CheckConstraint(
            "purge_gap_size >= max_feature_window",
            name="ck_validation_runs_sufficient_purge",
        ),
        CheckConstraint(
            (
                "source_observation_count > 0 AND split_count > 0 "
                "AND development_range_start <= development_range_end "
                "AND development_range_end < final_holdout_start "
                "AND final_holdout_start <= final_holdout_end"
            ),
            name="ck_validation_runs_valid_ranges",
        ),
        CheckConstraint(
            (
                "char_length(configuration_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(source_data_hash) = 64"
            ),
            name="ck_validation_runs_hash_lengths",
        ),
        CheckConstraint(
            "holdout_excluded",
            name="ck_validation_runs_holdout_excluded",
        ),
        Index(
            "ix_validation_runs_configuration_hash",
            "configuration_hash",
        ),
        Index(
            "ix_validation_runs_source_ingestion_batch_id",
            "source_ingestion_batch_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_feature_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feature_pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    source_data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    minimum_train_size: Mapped[int] = mapped_column(Integer, nullable=False)
    test_size: Mapped[int] = mapped_column(Integer, nullable=False)
    step_size: Mapped[int] = mapped_column(Integer, nullable=False)
    purge_gap_size: Mapped[int] = mapped_column(Integer, nullable=False)
    final_holdout_size: Mapped[int] = mapped_column(Integer, nullable=False)
    max_feature_window: Mapped[int] = mapped_column(Integer, nullable=False)
    development_range_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    development_range_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    final_holdout_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    final_holdout_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    holdout_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    split_count: Mapped[int] = mapped_column(Integer, nullable=False)
    split_boundaries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    lookback_separation: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ForwardLogReturnTargetRunRecord(Base):
    __tablename__ = "forward_log_return_target_runs"
    __table_args__ = (
        CheckConstraint(
            (
                "horizon > 0 AND source_candle_count > horizon "
                "AND generated_label_count > 0 "
                "AND persisted_label_count >= 0 "
                "AND persisted_label_count <= generated_label_count "
                "AND excluded_observation_count >= 0 "
                "AND source_candle_count = "
                "generated_label_count + excluded_observation_count"
            ),
            name="ck_forward_log_return_runs_valid_counts",
        ),
        CheckConstraint(
            (
                "positive_label_count >= 0 AND negative_label_count >= 0 "
                "AND zero_label_count >= 0 "
                "AND generated_label_count = positive_label_count "
                "+ negative_label_count + zero_label_count"
            ),
            name="ck_forward_log_return_runs_valid_sign_counts",
        ),
        CheckConstraint(
            (
                "source_range_start <= first_eligible_timestamp "
                "AND first_eligible_timestamp <= last_eligible_timestamp "
                "AND last_eligible_timestamp < source_range_end"
            ),
            name="ck_forward_log_return_runs_valid_ranges",
        ),
        CheckConstraint(
            (
                "char_length(target_definition_hash) = 64 "
                "AND char_length(dataset_hash) = 64 "
                "AND char_length(label_data_hash) = 64"
            ),
            name="ck_forward_log_return_runs_hash_lengths",
        ),
        CheckConstraint(
            "point_in_time_validated",
            name="ck_forward_log_return_runs_point_in_time_validated",
        ),
        Index(
            "ix_forward_log_return_runs_source_ingestion_batch_id",
            "source_ingestion_batch_id",
        ),
        Index(
            "ix_forward_log_return_runs_source_feature_run_id",
            "source_feature_run_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    target_name: Mapped[str] = mapped_column(String(64), nullable=False)
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    target_definition_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_feature_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feature_pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    label_data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_range_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    source_range_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    generated_label_count: Mapped[int] = mapped_column(Integer, nullable=False)
    persisted_label_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    exclusion_details: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    first_eligible_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_eligible_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    label_value_min: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    label_value_max: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    label_value_mean: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    positive_label_count: Mapped[int] = mapped_column(Integer, nullable=False)
    negative_label_count: Mapped[int] = mapped_column(Integer, nullable=False)
    zero_label_count: Mapped[int] = mapped_column(Integer, nullable=False)
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ForwardLogReturnTargetRecord(Base):
    __tablename__ = "forward_log_return_targets"
    __table_args__ = (
        UniqueConstraint(
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "prediction_timestamp",
            "target_name",
            "target_version",
            name="uq_forward_log_return_targets_identity",
        ),
        CheckConstraint(
            "horizon > 0 AND prediction_timestamp < label_available_at",
            name="ck_forward_log_return_targets_valid_horizon",
        ),
        CheckConstraint(
            "char_length(dataset_hash) = 64",
            name="ck_forward_log_return_targets_dataset_hash_length",
        ),
        CheckConstraint(
            (
                "timeframe <> '1d' OR "
                "(prediction_timestamp = "
                "(date_trunc('day', prediction_timestamp AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC') "
                "AND label_available_at = "
                "(date_trunc('day', label_available_at AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC'))"
            ),
            name="ck_forward_log_return_targets_daily_utc_alignment",
        ),
        Index(
            "ix_forward_log_return_targets_generation_run_id",
            "generation_run_id",
        ),
        Index(
            "ix_forward_log_return_targets_source_ingestion_batch_id",
            "source_ingestion_batch_id",
        ),
        Index(
            "ix_forward_log_return_targets_source_feature_run_id",
            "source_feature_run_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    asset_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    target_name: Mapped[str] = mapped_column(String(64), nullable=False)
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prediction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    label_available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    target_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    source_ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_feature_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feature_pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "forward_log_return_target_runs.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RegressionExperimentRecord(Base):
    __tablename__ = "regression_experiments"
    __table_args__ = (
        CheckConstraint(
            (
                "model_family IN "
                "('linear_regression', 'ridge_regression', "
                "'random_forest_regression', 'xgboost_regression')"
            ),
            name="ck_regression_experiments_model_family",
        ),
        CheckConstraint(
            (
                "source_observation_count > 0 "
                "AND model_eligible_observation_count > 0 "
                "AND development_eligible_observation_count > 0 "
                "AND holdout_eligible_observation_count >= 0 "
                "AND excluded_feature_warmup_count >= 0 "
                "AND excluded_missing_target_count >= 0 "
                "AND model_eligible_observation_count = "
                "development_eligible_observation_count "
                "+ holdout_eligible_observation_count "
                "AND source_observation_count = "
                "model_eligible_observation_count "
                "+ excluded_feature_warmup_count "
                "+ excluded_missing_target_count"
            ),
            name="ck_regression_experiments_dataset_counts",
        ),
        CheckConstraint(
            (
                "validation_split_count > 0 "
                "AND evaluated_split_count > 0 "
                "AND skipped_split_count >= 0 "
                "AND validation_split_count = "
                "evaluated_split_count + skipped_split_count "
                "AND evaluated_observation_count > 0"
            ),
            name="ck_regression_experiments_evaluation_counts",
        ),
        CheckConstraint(
            (
                "aggregate_mae >= 0 AND aggregate_rmse >= 0 "
                "AND aggregate_directional_accuracy BETWEEN 0 AND 1"
            ),
            name="ck_regression_experiments_metric_ranges",
        ),
        CheckConstraint(
            (
                "char_length(source_dataset_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(target_definition_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(training_code_hash) = 64 "
                "AND char_length(experiment_configuration_hash) = 64 "
                "AND char_length(result_hash) = 64"
            ),
            name="ck_regression_experiments_hash_lengths",
        ),
        CheckConstraint(
            "point_in_time_validated AND NOT final_holdout_evaluated",
            name="ck_regression_experiments_research_safeguards",
        ),
        Index(
            "ix_regression_experiments_validation_run_id",
            "validation_run_id",
        ),
        Index(
            "ix_regression_experiments_source_target_run_id",
            "source_target_run_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)
    model_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    preprocessing_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    evaluation_policy_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    random_seeds: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    training_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    training_code_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    source_ingestion_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("market_data_ingestion_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_feature_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feature_pipeline_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_target_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "forward_log_return_target_runs.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    feature_names: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    target_name: Mapped[str] = mapped_column(String(64), nullable=False)
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    target_definition_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    model_eligible_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    development_eligible_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    holdout_eligible_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    excluded_feature_warmup_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    excluded_missing_target_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    validation_split_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evaluated_split_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    skipped_split_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evaluated_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    aggregate_mae: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    aggregate_rmse: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    aggregate_directional_accuracy: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    aggregation_method: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    software_versions: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
    )
    experiment_configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RegressionExperimentSplitRecord(Base):
    __tablename__ = "regression_experiment_splits"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id",
            "split_sequence",
            name="uq_regression_experiment_splits_sequence",
        ),
        CheckConstraint(
            (
                "split_sequence > 0 "
                "AND train_start <= train_end "
                "AND train_end < test_start "
                "AND test_start <= test_end "
                "AND train_observation_count >= 0 "
                "AND test_observation_count >= 0"
            ),
            name="ck_regression_experiment_splits_ranges",
        ),
        CheckConstraint(
            (
                "(status = 'evaluated' "
                "AND exclusion_reason IS NULL "
                "AND train_observation_count > 0 "
                "AND test_observation_count > 0 "
                "AND latest_train_label_available_at IS NOT NULL "
                "AND latest_train_label_available_at < test_start "
                "AND mae IS NOT NULL AND mae >= 0 "
                "AND rmse IS NOT NULL AND rmse >= 0 "
                "AND directional_accuracy IS NOT NULL "
                "AND directional_accuracy BETWEEN 0 AND 1 "
                "AND char_length(prediction_hash) = 64) "
                "OR (status = 'skipped' "
                "AND exclusion_reason IS NOT NULL "
                "AND mae IS NULL AND rmse IS NULL "
                "AND directional_accuracy IS NULL "
                "AND prediction_hash IS NULL)"
            ),
            name="ck_regression_experiment_splits_status",
        ),
        Index(
            "ix_regression_experiment_splits_experiment_id",
            "experiment_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    train_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    train_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    test_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    test_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    train_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    test_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(
        String(96),
        nullable=True,
    )
    latest_train_label_available_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    mae: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18),
        nullable=True,
    )
    rmse: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18),
        nullable=True,
    )
    directional_accuracy: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18),
        nullable=True,
    )
    prediction_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )


class ModelComparisonReportRecord(Base):
    __tablename__ = "model_comparison_reports"
    __table_args__ = (
        CheckConstraint(
            (
                "model_count = 4 "
                "AND char_length(report_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND NOT final_holdout_evaluated"
            ),
            name="ck_model_comparison_reports_integrity",
        ),
        UniqueConstraint(
            "report_hash",
            name="uq_model_comparison_reports_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    model_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_policy_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_evidence_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ModelComparisonReportExperimentRecord(Base):
    __tablename__ = "model_comparison_report_experiments"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_model_comparison_report_experiments_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("model_comparison_reports.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class ModelExplainabilityArtifactRecord(Base):
    __tablename__ = "model_explainability_artifacts"
    __table_args__ = (
        CheckConstraint(
            (
                "model_family IN "
                "('random_forest_regression', 'xgboost_regression') "
                "AND permutation_random_seed = 42 "
                "AND permutation_repeats > 0 "
                "AND evaluated_split_count > 0 "
                "AND evaluated_observation_count > 0 "
                "AND prediction_hashes_verified = evaluated_split_count "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated"
            ),
            name="ck_model_explainability_artifacts_integrity",
        ),
        UniqueConstraint(
            "experiment_id",
            "configuration_hash",
            "result_hash",
            name="uq_model_explainability_artifacts_result",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    method_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    artifact_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    permutation_random_seed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    permutation_repeats: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evaluated_split_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evaluated_observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    prediction_hashes_verified: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StatisticalValidationReportRecord(Base):
    __tablename__ = "statistical_validation_reports"
    __table_args__ = (
        CheckConstraint(
            (
                "bootstrap_random_seed = 42 "
                "AND bootstrap_resamples > 0 "
                "AND confidence_level = 0.95 "
                "AND model_count = 4 "
                "AND pair_count = 6 "
                "AND hypothesis_count = 18 "
                "AND evaluated_fold_count > 0 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated "
                "AND NOT model_retraining_performed"
            ),
            name="ck_statistical_validation_reports_integrity",
        ),
        UniqueConstraint(
            "configuration_hash",
            "result_hash",
            name="uq_statistical_validation_reports_result",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bootstrap_random_seed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    bootstrap_resamples: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    confidence_level: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )
    model_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    hypothesis_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluated_fold_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    model_retraining_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StatisticalValidationReportExperimentRecord(Base):
    __tablename__ = "statistical_validation_report_experiments"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_statistical_validation_report_experiments_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("statistical_validation_reports.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class StatisticalValidationReportExplainabilityRecord(Base):
    __tablename__ = "statistical_validation_report_explainability"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_statistical_validation_report_explainability_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("statistical_validation_reports.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "model_explainability_artifacts.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class ExperimentPredictionEvidenceRecord(Base):
    __tablename__ = "experiment_prediction_evidence"
    __table_args__ = (
        CheckConstraint(
            (
                "split_sequence > 0 "
                "AND observation_index > 0 "
                "AND char_length(source_prediction_hash) = 64 "
                "AND char_length(evidence_hash) = 64 "
                "AND char_length(actual_float_hex) > 0 "
                "AND char_length(predicted_float_hex) > 0 "
                "AND char_length(residual_float_hex) > 0"
            ),
            name="ck_experiment_prediction_evidence_integrity",
        ),
        UniqueConstraint(
            "experiment_id",
            "prediction_timestamp",
            name="uq_experiment_prediction_evidence_timestamp",
        ),
        UniqueConstraint(
            "evidence_hash",
            name="uq_experiment_prediction_evidence_hash",
        ),
        Index(
            "ix_experiment_prediction_evidence_experiment_split",
            "experiment_split_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    experiment_split_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "regression_experiment_splits.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)
    split_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prediction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    actual_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    predicted_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    residual_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18),
        nullable=False,
    )
    actual_float_hex: Mapped[str] = mapped_column(String(32), nullable=False)
    predicted_float_hex: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    residual_float_hex: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    source_prediction_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ResidualDiagnosticsReportRecord(Base):
    __tablename__ = "residual_diagnostics_reports"
    __table_args__ = (
        CheckConstraint(
            (
                "model_count = 4 "
                "AND evaluated_split_count > 0 "
                "AND evaluated_observation_count_per_model > 0 "
                "AND prediction_evidence_count = "
                "model_count * evaluated_observation_count_per_model "
                "AND prediction_hashes_verified = "
                "model_count * evaluated_split_count "
                "AND plot_count = 16 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND deterministic_replay_performed "
                "AND NOT experiments_modified "
                "AND NOT final_holdout_evaluated"
            ),
            name="ck_residual_diagnostics_reports_integrity",
        ),
        UniqueConstraint(
            "configuration_hash",
            "result_hash",
            name="uq_residual_diagnostics_reports_result",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    statistical_validation_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "statistical_validation_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluated_split_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evaluated_observation_count_per_model: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    prediction_evidence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    prediction_hashes_verified: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    plot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    deterministic_replay_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    experiments_modified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ResidualDiagnosticsReportExperimentRecord(Base):
    __tablename__ = "residual_diagnostics_report_experiments"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_residual_diagnostics_report_experiments_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("residual_diagnostics_reports.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class ResidualDiagnosticsReportExplainabilityRecord(Base):
    __tablename__ = "residual_diagnostics_report_explainability"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_residual_diagnostics_report_explainability_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("residual_diagnostics_reports.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "model_explainability_artifacts.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class ResidualDiagnosticPlotRecord(Base):
    __tablename__ = "residual_diagnostic_plots"
    __table_args__ = (
        CheckConstraint(
            (
                "plot_type IN "
                "('residual_histogram', 'residual_qq', "
                "'residual_vs_predicted', 'residual_vs_actual') "
                "AND mime_type = 'image/svg+xml' "
                "AND char_length(content_hash) = 64 "
                "AND char_length(content) > 0"
            ),
            name="ck_residual_diagnostic_plots_integrity",
        ),
        UniqueConstraint(
            "report_id",
            "model_family",
            "plot_type",
            name="uq_residual_diagnostic_plots_report_model_type",
        ),
        UniqueConstraint(
            "content_hash",
            name="uq_residual_diagnostic_plots_content_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("residual_diagnostics_reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)
    plot_type: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MarketRegimeAnalysisReportRecord(Base):
    __tablename__ = "market_regime_analysis_reports"
    __table_args__ = (
        CheckConstraint(
            (
                "model_count = 4 "
                "AND assignment_count > 0 "
                "AND prediction_evidence_count = model_count * "
                "assignment_count "
                "AND evaluated_split_count > 0 "
                "AND plot_count = 12 "
                "AND char_length(regime_assignment_set_hash) = 64 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated "
                "AND NOT model_retraining_performed "
                "AND NOT experiments_modified"
            ),
            name="ck_market_regime_analysis_reports_integrity",
        ),
        UniqueConstraint(
            "configuration_hash",
            "result_hash",
            name="uq_market_regime_analysis_reports_result",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    regime_assignment_set_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    statistical_validation_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "statistical_validation_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    residual_diagnostics_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "residual_diagnostics_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_count: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prediction_evidence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    evaluated_split_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    plot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    model_retraining_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    experiments_modified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MarketRegimeReportExperimentRecord(Base):
    __tablename__ = "market_regime_report_experiments"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_market_regime_report_experiments_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "market_regime_analysis_reports.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class MarketRegimeReportExplainabilityRecord(Base):
    __tablename__ = "market_regime_report_explainability"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_market_regime_report_explainability_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "market_regime_analysis_reports.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "model_explainability_artifacts.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class MarketRegimeAssignmentRecord(Base):
    __tablename__ = "market_regime_assignments"
    __table_args__ = (
        CheckConstraint(
            (
                "trend_regime IN "
                "('bull_trend', 'bear_trend', 'sideways_market') "
                "AND volatility_regime IN "
                "('high_volatility_regime', 'low_volatility_regime') "
                "AND char_length(trend_spread) > 0 "
                "AND char_length(bollinger_relative_width) > 0 "
                "AND char_length(expanding_width_median) > 0 "
                "AND char_length(assignment_hash) = 64"
            ),
            name="ck_market_regime_assignments_integrity",
        ),
        UniqueConstraint(
            "report_id",
            "prediction_timestamp",
            name="uq_market_regime_assignments_timestamp",
        ),
        UniqueConstraint(
            "report_id",
            "assignment_hash",
            name="uq_market_regime_assignments_hash",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "market_regime_analysis_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    prediction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    trend_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    volatility_regime: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    trend_spread: Mapped[str] = mapped_column(String(96), nullable=False)
    bollinger_relative_width: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
    )
    expanding_width_median: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
    )
    assignment_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )


class MarketRegimePlotRecord(Base):
    __tablename__ = "market_regime_plots"
    __table_args__ = (
        CheckConstraint(
            (
                "plot_type IN "
                "('performance_by_regime', 'error_by_regime', "
                "'residual_distribution_by_regime') "
                "AND mime_type = 'image/svg+xml' "
                "AND char_length(content_hash) = 64 "
                "AND char_length(content) > 0"
            ),
            name="ck_market_regime_plots_integrity",
        ),
        UniqueConstraint(
            "report_id",
            "model_family",
            "plot_type",
            name="uq_market_regime_plots_report_model_type",
        ),
        UniqueConstraint(
            "content_hash",
            name="uq_market_regime_plots_content_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "market_regime_analysis_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)
    plot_type: Mapped[str] = mapped_column(String(48), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class FinalModelSelectionReportRecord(Base):
    __tablename__ = "final_model_selection_reports"
    __table_args__ = (
        CheckConstraint(
            (
                "model_count = 4 "
                "AND selected_model_family IN "
                "('linear_regression', 'ridge_regression', "
                "'random_forest_regression', 'xgboost_regression') "
                "AND selected_model_rank = 1 "
                "AND source_artifact_count = 6 "
                "AND source_plot_hash_count = 28 "
                "AND prediction_evidence_count > 0 "
                "AND prediction_hashes_verified > 0 "
                "AND automated_test_count > 0 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND artifact_hashes_verified "
                "AND repeatability_verified "
                "AND automated_tests_passed "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated "
                "AND NOT model_retraining_performed "
                "AND NOT experiments_modified "
                "AND NOT new_experimental_evidence_created"
            ),
            name="ck_final_model_selection_reports_integrity",
        ),
        UniqueConstraint(
            "configuration_hash",
            "result_hash",
            name="uq_final_model_selection_reports_result",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    report_version: Mapped[str] = mapped_column(String(32), nullable=False)
    report_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    report_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_comparison_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("model_comparison_reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    statistical_validation_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "statistical_validation_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    residual_diagnostics_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "residual_diagnostics_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    market_regime_analysis_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "market_regime_analysis_reports.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    selected_experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_model_family: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    selected_model_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    model_dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    feature_pipeline_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_version: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_artifact_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    source_plot_hash_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    prediction_evidence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    prediction_hashes_verified: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    automated_test_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    artifact_hashes_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    repeatability_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    automated_tests_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    point_in_time_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    final_holdout_evaluated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    model_retraining_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    experiments_modified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    new_experimental_evidence_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class FinalModelSelectionReportExperimentRecord(Base):
    __tablename__ = "final_model_selection_report_experiments"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_final_model_selection_report_experiments_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "final_model_selection_reports.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    experiment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regression_experiments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)


class FinalModelSelectionReportExplainabilityRecord(Base):
    __tablename__ = "final_model_selection_report_explainability"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_final_model_selection_report_explainability_family",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "final_model_selection_reports.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    artifact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "model_explainability_artifacts.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )
    model_family: Mapped[str] = mapped_column(String(32), nullable=False)
