"""Immutable deterministic backtest report construction."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

from app.backtesting.metrics import calculate_performance_metrics
from app.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)


BACKTEST_ENGINE_VERSION = "1.0.0"
BACKTEST_REPORT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class BacktestProvenance:
    holdout_evaluation_report_id: UUID
    holdout_configuration_hash: str
    holdout_result_hash: str
    selected_experiment_id: UUID
    selected_experiment_configuration_hash: str
    selected_experiment_result_hash: str
    model_dataset_hash: str
    feature_pipeline_version: str
    target_version: str
    validation_run_id: UUID
    split_hash: str
    prediction_evidence_set_hash: str
    candle_ingestion_batch_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class BuiltBacktestReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    input_evidence_hash: str
    signal_hash: str
    trade_log_hash: str
    equity_curve_hash: str
    daily_history_hash: str


def build_backtest_report(
    *,
    configuration: BacktestConfig,
    strategy_configuration: StrategyConfig,
    provenance: BacktestProvenance,
    predictions: tuple[PredictionPoint, ...],
    bars: tuple[MarketBar, ...],
    result: BacktestResult,
) -> BuiltBacktestReport:
    """Build a content-addressed report without timestamps or random IDs."""
    configuration_payload = {
        "report_version": BACKTEST_REPORT_VERSION,
        "engine_version": BACKTEST_ENGINE_VERSION,
        "execution_chronology": {
            "prediction_available": "after_completed_daily_close",
            "strategy_execution": "next_observation_open",
            "terminal_liquidation": (
                "final_observation_close_when_enabled"
            ),
        },
        "portfolio": _serialize(asdict(configuration)),
        "strategy": _serialize(asdict(strategy_configuration)),
        "provenance": _provenance_payload(provenance),
    }
    signals = [_signal_payload(item) for item in result.signals]
    fills = [_fill_payload(item) for item in result.fills]
    trades = [_trade_payload(item) for item in result.closed_trades]
    daily_history = [
        _daily_payload(item) for item in result.daily_history
    ]
    equity_curve = [
        {
            "timestamp": item.timestamp.isoformat(),
            "portfolio_value": _decimal(item.portfolio_value),
        }
        for item in result.daily_history
    ]
    input_evidence_hash = _hash_json(
        {
            "predictions": [
                {
                    "prediction_timestamp": (
                        item.prediction_timestamp.isoformat()
                    ),
                    "predicted_forward_return": _decimal(
                        item.predicted_forward_return
                    ),
                    "evidence_hash": item.evidence_hash,
                }
                for item in predictions
            ],
            "bars": [
                {
                    "timestamp": item.timestamp.isoformat(),
                    "open": _decimal(item.open_price),
                    "high": _decimal(item.high_price),
                    "low": _decimal(item.low_price),
                    "close": _decimal(item.close_price),
                }
                for item in bars
            ],
        }
    )
    signal_hash = _hash_json(signals)
    trade_log_hash = _hash_json(trades)
    equity_curve_hash = _hash_json(equity_curve)
    daily_history_hash = _hash_json(daily_history)
    metrics = _serialize(
        calculate_performance_metrics(result, configuration)
    )
    payload = {
        "report_version": BACKTEST_REPORT_VERSION,
        "engine_version": BACKTEST_ENGINE_VERSION,
        "configuration": configuration_payload,
        "metrics": metrics,
        "signals": signals,
        "execution_fills": fills,
        "trade_log": trades,
        "equity_curve": equity_curve,
        "daily_portfolio_history": daily_history,
        "provenance": _provenance_payload(provenance),
        "artifact_hashes": {
            "input_evidence_sha256": input_evidence_hash,
            "signals_sha256": signal_hash,
            "trade_log_sha256": trade_log_hash,
            "equity_curve_sha256": equity_curve_hash,
            "daily_portfolio_history_sha256": daily_history_hash,
            "source_prediction_evidence_set_sha256": (
                provenance.prediction_evidence_set_hash
            ),
        },
        "verification": {
            "research_artifacts_modified": False,
            "model_retrained": False,
            "model_tuned": False,
            "new_model_created": False,
            "signals_derived_only_from_predictions": True,
            "next_observation_execution_enforced": True,
            "long_only": configuration.long_only,
            "deterministic": True,
        },
    }
    return BuiltBacktestReport(
        configuration=configuration_payload,
        configuration_hash=_hash_json(configuration_payload),
        payload=payload,
        result_hash=_hash_json(payload),
        input_evidence_hash=input_evidence_hash,
        signal_hash=signal_hash,
        trade_log_hash=trade_log_hash,
        equity_curve_hash=equity_curve_hash,
        daily_history_hash=daily_history_hash,
    )


def _provenance_payload(
    provenance: BacktestProvenance,
) -> dict[str, Any]:
    return {
        "holdout_evaluation_report_id": str(
            provenance.holdout_evaluation_report_id
        ),
        "holdout_configuration_hash": (
            provenance.holdout_configuration_hash
        ),
        "holdout_result_hash": provenance.holdout_result_hash,
        "selected_experiment_id": str(
            provenance.selected_experiment_id
        ),
        "selected_experiment_configuration_hash": (
            provenance.selected_experiment_configuration_hash
        ),
        "selected_experiment_result_hash": (
            provenance.selected_experiment_result_hash
        ),
        "model_dataset_hash": provenance.model_dataset_hash,
        "feature_pipeline_version": provenance.feature_pipeline_version,
        "target_version": provenance.target_version,
        "validation_run_id": str(provenance.validation_run_id),
        "split_hash": provenance.split_hash,
        "prediction_evidence_set_hash": (
            provenance.prediction_evidence_set_hash
        ),
        "candle_ingestion_batch_ids": [
            str(item)
            for item in sorted(
                provenance.candle_ingestion_batch_ids,
                key=str,
            )
        ],
    }


def _signal_payload(item) -> dict[str, Any]:
    return {
        "prediction_timestamp": item.prediction_timestamp.isoformat(),
        "action": item.action.value,
        "predicted_forward_return": _decimal(
            item.predicted_forward_return
        ),
        "strategy_name": item.strategy_name,
        "strategy_version": item.strategy_version,
        "source_prediction_hash": item.source_prediction_hash,
    }


def _fill_payload(item) -> dict[str, Any]:
    return {
        "signal_timestamp": item.signal_timestamp.isoformat(),
        "execution_timestamp": item.execution_timestamp.isoformat(),
        "side": item.side.value,
        "reference_price": _decimal(item.reference_price),
        "execution_price": _decimal(item.execution_price),
        "quantity": _decimal(item.quantity),
        "gross_notional": _decimal(item.gross_notional),
        "transaction_cost": _decimal(item.transaction_cost),
        "cash_delta": _decimal(item.cash_delta),
        "reason": item.reason,
    }


def _trade_payload(item) -> dict[str, Any]:
    return {
        "entry_signal_timestamp": (
            item.entry_signal_timestamp.isoformat()
        ),
        "entry_timestamp": item.entry_timestamp.isoformat(),
        "exit_signal_timestamp": (
            item.exit_signal_timestamp.isoformat()
            if item.exit_signal_timestamp is not None
            else None
        ),
        "exit_timestamp": item.exit_timestamp.isoformat(),
        "quantity": _decimal(item.quantity),
        "entry_price": _decimal(item.entry_price),
        "exit_price": _decimal(item.exit_price),
        "gross_profit_loss": _decimal(item.gross_profit_loss),
        "net_profit_loss": _decimal(item.net_profit_loss),
        "total_transaction_cost": _decimal(
            item.total_transaction_cost
        ),
        "return_fraction": _decimal(item.return_fraction),
        "holding_days": item.holding_days,
        "exit_reason": item.exit_reason,
    }


def _daily_payload(item) -> dict[str, Any]:
    return {
        "timestamp": item.timestamp.isoformat(),
        "cash": _decimal(item.cash),
        "position_quantity": _decimal(item.position_quantity),
        "position_market_value": _decimal(item.position_market_value),
        "portfolio_value": _decimal(item.portfolio_value),
        "daily_return": _decimal(item.daily_return),
        "open_position_count": item.open_position_count,
    }


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal(value)
    if isinstance(value, dict):
        return {
            str(key): _serialize(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    return value


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def hash_json(value: object) -> str:
    """Return the canonical SHA-256 used by persisted backtest evidence."""
    return _hash_json(value)


def _hash_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

