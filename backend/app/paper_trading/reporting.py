"""Immutable content-addressed paper trading reports."""

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from app.backtesting.models import (
    ClosedTrade,
    ExecutionFill,
    OrderSide,
    PortfolioSnapshot,
    SignalAction,
    TradingSignal,
)
from app.backtesting.risk.models import (
    RiskEvent,
    RiskEventType,
)
from app.paper_trading.audit import hash_json
from app.paper_trading.models import (
    PAPER_TRADING_ENGINE_VERSION,
    PAPER_TRADING_REPORT_VERSION,
    PaperAuditEvent,
    PaperCycleResult,
    PaperPosition,
    PaperPrediction,
    PaperTradingConfiguration,
    PaperTradingProvenance,
    PaperTradingState,
)
from app.paper_trading.performance import PaperPerformanceTracker


@dataclass(frozen=True, slots=True)
class BuiltPaperTradingReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    prediction_hash: str
    signal_hash: str
    order_hash: str
    trade_hash: str
    risk_event_hash: str
    portfolio_history_hash: str
    audit_log_hash: str


def build_paper_trading_report(
    *,
    configuration: PaperTradingConfiguration,
    provenance: PaperTradingProvenance,
    cycle: PaperCycleResult,
    previous_report_id: UUID | None,
    previous_result_hash: str | None,
) -> BuiltPaperTradingReport:
    state = cycle.state
    configuration_payload = paper_trading_configuration_payload(
        configuration=configuration,
        provenance=provenance,
    )
    predictions = [_prediction_payload(item) for item in state.predictions]
    signals = [_signal_payload(item) for item in state.signals]
    orders = [_fill_payload(item) for item in state.fills]
    trades = [_trade_payload(item) for item in state.closed_trades]
    risks = [_risk_payload(item) for item in state.risk_events]
    history = [
        _portfolio_payload(item) for item in state.portfolio_history
    ]
    audit = [_audit_payload(item) for item in state.audit_log]
    hashes = {
        "market_data_sha256": cycle.market_data_hash,
        "cycle_feature_vectors_sha256": cycle.feature_set_hash,
        "cycle_predictions_sha256": cycle.prediction_set_hash,
        "predictions_sha256": hash_json(predictions),
        "signals_sha256": hash_json(signals),
        "orders_sha256": hash_json(orders),
        "trades_sha256": hash_json(trades),
        "risk_events_sha256": hash_json(risks),
        "portfolio_history_sha256": hash_json(history),
        "audit_log_sha256": hash_json(audit),
        "inference_artifact_sha256": (
            provenance.inference_artifact_sha256
        ),
    }
    payload = {
        "report_version": PAPER_TRADING_REPORT_VERSION,
        "engine_version": PAPER_TRADING_ENGINE_VERSION,
        "configuration": configuration_payload,
        "cycle": {
            "processed_observation_count": (
                cycle.processed_observation_count
            ),
            "start": cycle.cycle_start.isoformat(),
            "end": cycle.cycle_end.isoformat(),
            "previous_report_id": (
                str(previous_report_id)
                if previous_report_id is not None
                else None
            ),
            "previous_result_hash": previous_result_hash,
        },
        "predictions": predictions,
        "signals": signals,
        "orders": orders,
        "trades": trades,
        "risk_events": risks,
        "portfolio_history": history,
        "performance_summary": _serialize(
            PaperPerformanceTracker().summarize(
                state,
                configuration,
            )
        ),
        "audit_log": audit,
        "state": _state_payload(state),
        "provenance": _provenance_payload(provenance),
        "artifact_hashes": hashes,
        "verification": {
            "artifact_only_inference": True,
            "fit_invoked": False,
            "model_retrained": False,
            "model_tuned": False,
            "research_artifacts_modified": False,
            "features_point_in_time_validated": True,
            "next_observation_execution_enforced": True,
            "risk_evaluated_before_orders": True,
            "live_broker_orders_placed": False,
            "deterministic": True,
        },
    }
    return BuiltPaperTradingReport(
        configuration=configuration_payload,
        configuration_hash=hash_json(configuration_payload),
        payload=payload,
        result_hash=hash_json(payload),
        prediction_hash=hashes["predictions_sha256"],
        signal_hash=hashes["signals_sha256"],
        order_hash=hashes["orders_sha256"],
        trade_hash=hashes["trades_sha256"],
        risk_event_hash=hashes["risk_events_sha256"],
        portfolio_history_hash=hashes[
            "portfolio_history_sha256"
        ],
        audit_log_hash=hashes["audit_log_sha256"],
    )


def paper_trading_configuration_payload(
    *,
    configuration: PaperTradingConfiguration,
    provenance: PaperTradingProvenance,
) -> dict[str, Any]:
    return {
        "report_version": PAPER_TRADING_REPORT_VERSION,
        "engine_version": PAPER_TRADING_ENGINE_VERSION,
        "paper_session": _serialize(asdict(configuration)),
        "execution_chronology": {
            "prediction_available": "after_completed_daily_close",
            "paper_order_execution": "next_observation_open",
            "same_close_execution": False,
            "live_broker_orders": False,
        },
        "provenance": _provenance_payload(provenance),
    }


def state_from_report(payload: dict[str, Any]) -> PaperTradingState:
    state = payload["state"]
    predictions = tuple(
        _prediction_from_payload(item)
        for item in payload["predictions"]
    )
    signals = tuple(
        _signal_from_payload(item) for item in payload["signals"]
    )
    fills = tuple(
        _fill_from_payload(item) for item in payload["orders"]
    )
    trades = tuple(
        _trade_from_payload(item) for item in payload["trades"]
    )
    risks = tuple(
        _risk_from_payload(item) for item in payload["risk_events"]
    )
    history = tuple(
        _portfolio_from_payload(item)
        for item in payload["portfolio_history"]
    )
    audit = tuple(
        _audit_from_payload(item) for item in payload["audit_log"]
    )
    return PaperTradingState(
        observation_sequence=int(state["observation_sequence"]),
        last_market_timestamp=_optional_datetime(
            state["last_market_timestamp"]
        ),
        cash=Decimal(state["cash"]),
        open_position=(
            _position_from_payload(state["open_position"])
            if state["open_position"] is not None
            else None
        ),
        pending_signal=(
            _signal_from_payload(state["pending_signal"])
            if state["pending_signal"] is not None
            else None
        ),
        portfolio_peak=Decimal(state["portfolio_peak"]),
        previous_close_equity=Decimal(
            state["previous_close_equity"]
        ),
        last_exit_observation_index=(
            int(state["last_exit_observation_index"])
            if state["last_exit_observation_index"] is not None
            else None
        ),
        predictions=predictions,
        signals=signals,
        fills=fills,
        closed_trades=trades,
        risk_events=risks,
        portfolio_history=history,
        audit_log=audit,
    )


def _state_payload(state: PaperTradingState) -> dict[str, Any]:
    return {
        "observation_sequence": state.observation_sequence,
        "last_market_timestamp": (
            state.last_market_timestamp.isoformat()
            if state.last_market_timestamp is not None
            else None
        ),
        "cash": _decimal(state.cash),
        "open_position": (
            {
                "entry_fill": _fill_payload(
                    state.open_position.entry_fill
                ),
                "high_watermark": _decimal(
                    state.open_position.high_watermark
                ),
            }
            if state.open_position is not None
            else None
        ),
        "pending_signal": (
            _signal_payload(state.pending_signal)
            if state.pending_signal is not None
            else None
        ),
        "portfolio_peak": _decimal(state.portfolio_peak),
        "previous_close_equity": _decimal(
            state.previous_close_equity
        ),
        "last_exit_observation_index": (
            state.last_exit_observation_index
        ),
    }


def _provenance_payload(
    item: PaperTradingProvenance,
) -> dict[str, Any]:
    return {
        "inference_artifact_id": str(item.inference_artifact_id),
        "inference_artifact_sha256": item.inference_artifact_sha256,
        "inference_state_sha256": item.inference_state_sha256,
        "inference_configuration_hash": (
            item.inference_configuration_hash
        ),
        "selected_experiment_id": str(item.selected_experiment_id),
        "holdout_evaluation_report_id": str(
            item.holdout_evaluation_report_id
        ),
        "model_dataset_hash": item.model_dataset_hash,
        "training_dataset_hash": item.training_dataset_hash,
        "feature_pipeline_version": item.feature_pipeline_version,
        "target_version": item.target_version,
        "validation_run_id": str(item.validation_run_id),
        "split_hash": item.split_hash,
    }


def _prediction_payload(item: PaperPrediction) -> dict[str, Any]:
    return {
        "prediction_timestamp": item.prediction_timestamp.isoformat(),
        "predicted_forward_return": _decimal(
            item.predicted_forward_return
        ),
        "predicted_float_hex": item.predicted_float_hex,
        "evidence_hash": item.evidence_hash,
        "feature_vector_hash": item.feature_vector_hash,
        "inference_artifact_sha256": (
            item.inference_artifact_sha256
        ),
    }


def _signal_payload(item: TradingSignal) -> dict[str, Any]:
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


def _fill_payload(item: ExecutionFill) -> dict[str, Any]:
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


def _trade_payload(item: ClosedTrade) -> dict[str, Any]:
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


def _risk_payload(item: RiskEvent) -> dict[str, Any]:
    return {
        "timestamp": item.timestamp.isoformat(),
        "event_type": item.event_type.value,
        "action": item.action,
        "rule_names": list(item.rule_names),
        "reason": item.reason,
        "requested_cash_allocation": _optional_decimal(
            item.requested_cash_allocation
        ),
        "approved_cash_allocation": _optional_decimal(
            item.approved_cash_allocation
        ),
        "reference_price": _optional_decimal(item.reference_price),
    }


def _portfolio_payload(item: PortfolioSnapshot) -> dict[str, Any]:
    return {
        "timestamp": item.timestamp.isoformat(),
        "cash": _decimal(item.cash),
        "position_quantity": _decimal(item.position_quantity),
        "position_market_value": _decimal(
            item.position_market_value
        ),
        "portfolio_value": _decimal(item.portfolio_value),
        "daily_return": _decimal(item.daily_return),
        "open_position_count": item.open_position_count,
    }


def _audit_payload(item: PaperAuditEvent) -> dict[str, Any]:
    return {
        "sequence": item.sequence,
        "observation_timestamp": (
            item.observation_timestamp.isoformat()
        ),
        "event_type": item.event_type,
        "evidence_hash": item.evidence_hash,
    }


def _prediction_from_payload(item: dict[str, Any]) -> PaperPrediction:
    return PaperPrediction(
        prediction_timestamp=datetime.fromisoformat(
            item["prediction_timestamp"]
        ),
        predicted_forward_return=Decimal(
            item["predicted_forward_return"]
        ),
        predicted_float_hex=item["predicted_float_hex"],
        evidence_hash=item["evidence_hash"],
        feature_vector_hash=item["feature_vector_hash"],
        inference_artifact_sha256=item["inference_artifact_sha256"],
    )


def _signal_from_payload(item: dict[str, Any]) -> TradingSignal:
    return TradingSignal(
        prediction_timestamp=datetime.fromisoformat(
            item["prediction_timestamp"]
        ),
        action=SignalAction(item["action"]),
        predicted_forward_return=Decimal(
            item["predicted_forward_return"]
        ),
        strategy_name=item["strategy_name"],
        strategy_version=item["strategy_version"],
        source_prediction_hash=item["source_prediction_hash"],
    )


def _fill_from_payload(item: dict[str, Any]) -> ExecutionFill:
    return ExecutionFill(
        signal_timestamp=datetime.fromisoformat(
            item["signal_timestamp"]
        ),
        execution_timestamp=datetime.fromisoformat(
            item["execution_timestamp"]
        ),
        side=OrderSide(item["side"]),
        reference_price=Decimal(item["reference_price"]),
        execution_price=Decimal(item["execution_price"]),
        quantity=Decimal(item["quantity"]),
        gross_notional=Decimal(item["gross_notional"]),
        transaction_cost=Decimal(item["transaction_cost"]),
        cash_delta=Decimal(item["cash_delta"]),
        reason=item["reason"],
    )


def _trade_from_payload(item: dict[str, Any]) -> ClosedTrade:
    return ClosedTrade(
        entry_signal_timestamp=datetime.fromisoformat(
            item["entry_signal_timestamp"]
        ),
        entry_timestamp=datetime.fromisoformat(item["entry_timestamp"]),
        exit_signal_timestamp=_optional_datetime(
            item["exit_signal_timestamp"]
        ),
        exit_timestamp=datetime.fromisoformat(item["exit_timestamp"]),
        quantity=Decimal(item["quantity"]),
        entry_price=Decimal(item["entry_price"]),
        exit_price=Decimal(item["exit_price"]),
        gross_profit_loss=Decimal(item["gross_profit_loss"]),
        net_profit_loss=Decimal(item["net_profit_loss"]),
        total_transaction_cost=Decimal(
            item["total_transaction_cost"]
        ),
        return_fraction=Decimal(item["return_fraction"]),
        holding_days=int(item["holding_days"]),
        exit_reason=item["exit_reason"],
    )


def _risk_from_payload(item: dict[str, Any]) -> RiskEvent:
    return RiskEvent(
        timestamp=datetime.fromisoformat(item["timestamp"]),
        event_type=RiskEventType(item["event_type"]),
        action=item["action"],
        rule_names=tuple(item["rule_names"]),
        reason=item["reason"],
        requested_cash_allocation=_optional_decimal_from_payload(
            item["requested_cash_allocation"]
        ),
        approved_cash_allocation=_optional_decimal_from_payload(
            item["approved_cash_allocation"]
        ),
        reference_price=_optional_decimal_from_payload(
            item["reference_price"]
        ),
    )


def _portfolio_from_payload(
    item: dict[str, Any],
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        timestamp=datetime.fromisoformat(item["timestamp"]),
        cash=Decimal(item["cash"]),
        position_quantity=Decimal(item["position_quantity"]),
        position_market_value=Decimal(item["position_market_value"]),
        portfolio_value=Decimal(item["portfolio_value"]),
        daily_return=Decimal(item["daily_return"]),
        open_position_count=int(item["open_position_count"]),
    )


def _audit_from_payload(item: dict[str, Any]) -> PaperAuditEvent:
    return PaperAuditEvent(
        sequence=int(item["sequence"]),
        observation_timestamp=datetime.fromisoformat(
            item["observation_timestamp"]
        ),
        event_type=item["event_type"],
        evidence_hash=item["evidence_hash"],
    )


def _position_from_payload(item: dict[str, Any]) -> PaperPosition:
    return PaperPosition(
        entry_fill=_fill_from_payload(item["entry_fill"]),
        high_watermark=Decimal(item["high_watermark"]),
    )


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal(value)
    if isinstance(value, Enum):
        return value.value
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


def _optional_decimal(value: Decimal | None) -> str | None:
    return _decimal(value) if value is not None else None


def _optional_decimal_from_payload(
    value: str | None,
) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _optional_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None
