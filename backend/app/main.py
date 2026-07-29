"""FastAPI application entry point."""

import asyncio
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import FastAPI
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
import uvicorn

from app.features.contracts import FeatureComputationError
from app.market_data.history import (
    HistoricalSample,
    fetch_btc_usd_daily_backfill,
    fetch_btc_usd_daily_sample,
)
from app.market_data.kraken import KrakenMarketDataProvider
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.persistence.candles import (
    get_stored_candle_summary,
    persist_historical_sample,
)
from app.persistence.database import session_factory
from app.persistence.features import (
    compute_and_persist_features,
    get_stored_feature_summary,
)
from app.persistence.experiments import run_and_persist_baseline_experiment
from app.persistence.targets import generate_and_persist_forward_log_returns
from app.persistence.validation import (
    ValidationRunAudit,
    create_validation_run,
    get_validation_run,
)
from app.settings import load_settings
from app.research.baseline_regression import BaselineExperimentError
from app.research.dataset import ResearchDatasetError
from app.targets.forward_log_return import TargetGenerationError
from app.validation.splits import (
    ValidationConfigurationError,
    WalkForwardConfig,
)


settings = load_settings()
market_data_provider: MarketDataProvider = KrakenMarketDataProvider(
    base_url=settings.market_data_base_url,
    timeout_seconds=settings.market_data_timeout_seconds,
)

app = FastAPI(
    title=settings.app_name,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/market-data/ping")
async def market_data_ping() -> dict[str, object]:
    try:
        quotes = await asyncio.gather(
            market_data_provider.get_current_quote("BTC"),
            market_data_provider.get_current_quote("ETH"),
        )
    except MarketDataProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"provider": "kraken", "quotes": quotes}


@app.get("/market-data/history/validate")
async def validate_market_data_history() -> dict[str, object]:
    try:
        sample = await fetch_btc_usd_daily_sample(market_data_provider)
    except MarketDataProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _historical_validation_response(sample)


@app.post("/market-data/history/ingest")
async def ingest_market_data_history(
    start: datetime | None = None,
    max_pages: int | None = None,
) -> dict[str, object]:
    try:
        sample = await fetch_btc_usd_daily_backfill(
            market_data_provider,
            requested_start=(
                start
                if start is not None
                else settings.history_backfill_start
            ),
            max_pages=(
                max_pages
                if max_pages is not None
                else settings.history_backfill_max_pages
            ),
        )
    except MarketDataProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        async with session_factory() as session:
            result = await persist_historical_sample(session, sample)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Market data persistence is unavailable.",
        ) from exc

    return {
        "ingestion_batch_id": result.ingestion_batch_id,
        "validation_passed": result.validation_passed,
        "validation_issue_count": len(sample.validation_report.issues),
        "fetched_candle_count": result.fetched_candle_count,
        "inserted_candle_count": result.persisted_candle_count,
        "stored_candle_count": result.stored_candle_count,
        "ingestion_batch_count": result.ingestion_batch_count,
        "available_range": {
            "start": (
                sample.candles[0].timestamp if sample.candles else None
            ),
            "end": (
                sample.candles[-1].timestamp if sample.candles else None
            ),
        },
        "pages_fetched": sample.pages_fetched,
        "provider_page_limit": sample.provider_page_limit,
        "provider_limit_reached": sample.provider_limit_reached,
        "pagination_exhausted": sample.pagination_exhausted,
        "excluded_incomplete_candle_count": (
            sample.excluded_incomplete_candle_count
        ),
        "excluded_pagination_overlap_count": (
            sample.excluded_pagination_overlap_count
        ),
        "progress": [
            {
                "page_number": progress.page_number,
                "requested_since": progress.requested_since,
                "provider_row_count": progress.provider_row_count,
                "accepted_completed_count": (
                    progress.accepted_completed_count
                ),
                "new_unique_completed_count": (
                    progress.new_unique_completed_count
                ),
                "excluded_incomplete_count": (
                    progress.excluded_incomplete_count
                ),
                "excluded_pagination_overlap_count": (
                    progress.excluded_pagination_overlap_count
                ),
                "cumulative_completed_count": (
                    progress.cumulative_completed_count
                ),
                "next_since": progress.next_since,
            }
            for progress in sample.progress
        ],
    }


@app.get("/market-data/history/stored")
async def read_stored_market_data_history() -> dict[str, object]:
    try:
        async with session_factory() as session:
            summary = await get_stored_candle_summary(session)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Stored market data is unavailable.",
        ) from exc

    return {
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "timeframe": "1d",
        "row_count": summary.row_count,
        "date_range": {
            "start": summary.date_range_start,
            "end": summary.date_range_end,
        },
        "latest_ingestion_batch_id": summary.latest_ingestion_batch_id,
        "latest_validation_passed": summary.latest_validation_passed,
        "latest_validation_issue_count": len(
            summary.latest_validation_issues
        ),
        "latest_validation_issues": summary.latest_validation_issues,
        "ingestion_batch_count": summary.ingestion_batch_count,
    }


@app.post("/features/compute")
async def compute_features() -> dict[str, object]:
    try:
        async with session_factory() as session:
            result = await compute_and_persist_features(session)
    except FeatureComputationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Feature persistence is unavailable.",
        ) from exc

    return {
        "computation_run_id": result.computation_run_id,
        "pipeline_version": result.pipeline_version,
        "source_ingestion_batch_id": result.source_ingestion_batch_id,
        "source_candle_count": result.source_candle_count,
        "source_range": {
            "start": result.source_range_start,
            "end": result.source_range_end,
        },
        "source_data_hash": result.source_data_hash,
        "point_in_time_validated": result.point_in_time_validated,
        "computed_value_count": result.computed_value_count,
        "inserted_value_count": result.inserted_value_count,
        "stored_value_count": result.stored_value_count,
    }


@app.get("/features/stored")
async def read_stored_features() -> dict[str, object]:
    try:
        async with session_factory() as session:
            summary = await get_stored_feature_summary(session)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Stored features are unavailable.",
        ) from exc

    return {
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "timeframe": "1d",
        "row_count": summary.row_count,
        "computation_run_count": summary.computation_run_count,
        "pipeline_versions": summary.pipeline_versions,
        "active_computation_run_id": summary.active_computation_run_id,
        "active_pipeline_version": summary.active_pipeline_version,
        "features": [
            {
                "feature_name": feature.feature_name,
                "row_count": feature.row_count,
                "earliest_timestamp": feature.earliest_timestamp,
                "latest_timestamp": feature.latest_timestamp,
                "latest_value": str(feature.latest_value),
            }
            for feature in summary.feature_series
        ],
    }


@app.post("/targets/forward-log-return/generate")
async def generate_forward_log_return_targets() -> dict[str, object]:
    try:
        async with session_factory() as session:
            result = await generate_and_persist_forward_log_returns(session)
    except TargetGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Target persistence is unavailable.",
        ) from exc

    return {
        "generation_run_id": result.generation_run_id,
        "target_name": result.target_name,
        "target_version": result.target_version,
        "target_definition_hash": result.target_definition_hash,
        "horizon": result.horizon,
        "source_ingestion_batch_id": result.source_ingestion_batch_id,
        "source_feature_run_id": result.source_feature_run_id,
        "feature_pipeline_version": result.feature_pipeline_version,
        "dataset_hash": result.dataset_hash,
        "label_data_hash": result.label_data_hash,
        "source_candle_count": result.source_candle_count,
        "generated_label_count": result.generated_label_count,
        "inserted_label_count": result.inserted_label_count,
        "stored_label_count": result.stored_label_count,
        "excluded_observation_count": result.excluded_observation_count,
        "exclusion_details": result.exclusion_details,
        "eligible_range": {
            "start": result.first_eligible_timestamp,
            "end": result.last_eligible_timestamp,
        },
        "label_statistics": {
            "minimum": str(result.minimum_value),
            "maximum": str(result.maximum_value),
            "mean": str(result.mean_value),
            "positive_count": result.positive_label_count,
            "negative_count": result.negative_label_count,
            "zero_count": result.zero_label_count,
        },
        "point_in_time_validated": result.point_in_time_validated,
        "execution_convention": {
            "information_cutoff": "after completed candle t",
            "same_close_execution_permitted": False,
            "earliest_interpretation": "next market observation",
        },
    }


@app.post("/validation/splits")
async def create_validation_splits(
    minimum_train_size: int = 20,
    test_size: int = 5,
    step_size: int = 5,
    purge_gap_size: int = 50,
    final_holdout_size: int = 10,
) -> dict[str, object]:
    config = WalkForwardConfig(
        minimum_train_size=minimum_train_size,
        test_size=test_size,
        step_size=step_size,
        purge_gap_size=purge_gap_size,
        final_holdout_size=final_holdout_size,
    )
    try:
        async with session_factory() as session:
            run = await create_validation_run(session, config)
    except (ValidationConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Validation run persistence is unavailable.",
        ) from exc

    return _validation_run_response(run)


@app.post("/research/baselines/{model_family}")
async def run_regression_baseline(
    model_family: Literal[
        "linear_regression",
        "ridge_regression",
        "random_forest_regression",
        "xgboost_regression",
    ],
) -> dict[str, object]:
    try:
        async with session_factory() as session:
            result = await run_and_persist_baseline_experiment(
                session,
                model_family,
            )
    except (BaselineExperimentError, ResearchDatasetError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Regression experiment persistence is unavailable.",
        ) from exc

    dataset = result.dataset
    evaluation = result.evaluation
    return {
        "experiment_id": result.experiment_id,
        "completed_at": result.completed_at,
        "model_family": evaluation.model_family,
        "model_parameters": evaluation.model_parameters,
        "preprocessing_parameters": (
            evaluation.preprocessing_parameters
        ),
        "evaluation_policy_parameters": (
            evaluation.evaluation_policy_parameters
        ),
        "random_seeds": evaluation.random_seeds,
        "training_pipeline_version": (
            evaluation.training_pipeline_version
        ),
        "training_code_hash": evaluation.training_code_hash,
        "provenance": {
            "source_ingestion_batch_id": (
                dataset.source_ingestion_batch_id
            ),
            "source_feature_run_id": dataset.source_feature_run_id,
            "source_target_run_id": dataset.source_target_run_id,
            "validation_run_id": dataset.validation_run_id,
            "source_dataset_hash": dataset.source_dataset_hash,
            "model_dataset_hash": dataset.model_dataset_hash,
            "feature_pipeline_version": (
                dataset.feature_pipeline_version
            ),
            "target_name": dataset.target_name,
            "target_version": dataset.target_version,
            "target_definition_hash": (
                dataset.target_definition_hash
            ),
            "split_hash": dataset.validation_split_hash,
        },
        "dataset": {
            "source_observation_count": (
                dataset.source_observation_count
            ),
            "total_eligible_observation_count": (
                dataset.total_eligible_observation_count
            ),
            "development_eligible_observation_count": (
                dataset.development_eligible_observation_count
            ),
            "holdout_eligible_observation_count": (
                dataset.holdout_eligible_observation_count
            ),
            "excluded_feature_warmup_count": (
                dataset.excluded_feature_warmup_count
            ),
            "excluded_missing_target_count": (
                dataset.excluded_missing_target_count
            ),
            "feature_names": dataset.feature_names,
        },
        "evaluation": {
            "validation_split_count": len(dataset.validation_splits),
            "evaluated_split_count": evaluation.evaluated_split_count,
            "skipped_split_count": evaluation.skipped_split_count,
            "evaluated_observation_count": (
                evaluation.evaluated_observation_count
            ),
            "aggregation_method": evaluation.aggregation_method,
            "aggregate_metrics": {
                "mae": str(evaluation.aggregate_mae),
                "rmse": str(evaluation.aggregate_rmse),
                "directional_accuracy": str(
                    evaluation.aggregate_directional_accuracy
                ),
            },
            "splits": [
                {
                    "sequence": split.sequence,
                    "train_range": {
                        "start": split.train_start,
                        "end": split.train_end,
                    },
                    "test_range": {
                        "start": split.test_start,
                        "end": split.test_end,
                    },
                    "train_observation_count": (
                        split.train_observation_count
                    ),
                    "test_observation_count": (
                        split.test_observation_count
                    ),
                    "status": split.status,
                    "exclusion_reason": split.exclusion_reason,
                    "latest_train_label_available_at": (
                        split.latest_train_label_available_at
                    ),
                    "mae": str(split.mae)
                    if split.mae is not None
                    else None,
                    "rmse": str(split.rmse)
                    if split.rmse is not None
                    else None,
                    "directional_accuracy": str(
                        split.directional_accuracy
                    )
                    if split.directional_accuracy is not None
                    else None,
                    "prediction_hash": split.prediction_hash,
                }
                for split in evaluation.split_evaluations
            ],
            "point_in_time_validated": (
                evaluation.point_in_time_validated
            ),
            "final_holdout_evaluated": (
                evaluation.final_holdout_evaluated
            ),
            "experiment_configuration_hash": (
                evaluation.experiment_configuration_hash
            ),
            "result_hash": evaluation.result_hash,
        },
    }


@app.get("/validation/runs/{run_id}")
async def read_validation_run(run_id: UUID) -> dict[str, object]:
    try:
        async with session_factory() as session:
            run = await get_validation_run(session, run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Validation run persistence is unavailable.",
        ) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found.")
    return _validation_run_response(run)


def _historical_validation_response(
    sample: HistoricalSample,
) -> dict[str, object]:
    candles = sample.candles
    report = sample.validation_report
    timestamped_candles = [
        candle for candle in candles if candle.timestamp is not None
    ]

    return {
        "provider": sample.provider,
        "asset_identifier": sample.asset_identifier,
        "quote_currency": sample.quote_currency,
        "timeframe": sample.timeframe.value,
        "candle_count": len(candles),
        "requested_range": {
            "start": sample.requested_start,
            "end_exclusive": sample.requested_end_exclusive,
        },
        "covered_range": {
            "start": timestamped_candles[0].timestamp
            if timestamped_candles
            else None,
            "end": timestamped_candles[-1].timestamp
            if timestamped_candles
            else None,
        },
        "first_candle": candles[0] if candles else None,
        "last_candle": candles[-1] if candles else None,
        "validation": {
            "passed": report.passed,
            "issue_count": len(report.issues),
            "issues": report.issues,
        },
    }


def _validation_run_response(
    run: ValidationRunAudit,
) -> dict[str, object]:
    return {
        "validation_run_id": run.id,
        "strategy": run.strategy,
        "asset_identifier": run.asset_identifier,
        "quote_currency": run.quote_currency,
        "timeframe": run.timeframe,
        "source_ingestion_batch_id": run.source_ingestion_batch_id,
        "source_feature_run_id": run.source_feature_run_id,
        "feature_pipeline_version": run.feature_pipeline_version,
        "source_data_hash": run.source_data_hash,
        "source_observation_count": run.source_observation_count,
        "configuration": {
            "minimum_train_size": run.minimum_train_size,
            "test_size": run.test_size,
            "step_size": run.step_size,
            "purge_gap_size": run.purge_gap_size,
            "final_holdout_size": run.final_holdout_size,
            "max_feature_window": run.max_feature_window,
        },
        "development_range": {
            "start": run.development_range_start,
            "end": run.development_range_end,
        },
        "final_holdout": {
            "start": run.final_holdout_start,
            "end": run.final_holdout_end,
            "excluded_from_iteration": run.holdout_excluded,
        },
        "split_count": run.split_count,
        "splits": run.split_boundaries,
        "lookback_separation": run.lookback_separation,
        "configuration_hash": run.configuration_hash,
        "split_hash": run.split_hash,
        "is_active": run.is_active,
        "superseded_at": run.superseded_at,
        "created_at": run.created_at,
    }


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
