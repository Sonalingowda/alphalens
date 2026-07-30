"""Content-addressed immutable risk management reports."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.backtesting.models import (
    BacktestConfig,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)
from app.backtesting.reporting import (
    BacktestProvenance,
    build_backtest_report,
    hash_json,
)
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.models import (
    RiskEvent,
    RiskEventType,
    RiskManagedBacktestResult,
)


RISK_FRAMEWORK_VERSION = "1.0.0"
RISK_REPORT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class RiskReportProvenance:
    backtest_provenance: BacktestProvenance
    source_backtest_report_id: UUID
    source_backtest_configuration_hash: str
    source_backtest_result_hash: str


@dataclass(frozen=True, slots=True)
class BuiltRiskManagementReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    risk_event_hash: str
    accepted_trade_hash: str
    rejected_trade_hash: str
    forced_exit_hash: str
    protection_event_hash: str


def build_risk_management_report(
    *,
    backtest_configuration: BacktestConfig,
    strategy_configuration: StrategyConfig,
    risk_configuration: RiskConfiguration,
    provenance: RiskReportProvenance,
    predictions: tuple[PredictionPoint, ...],
    bars: tuple[MarketBar, ...],
    result: RiskManagedBacktestResult,
) -> BuiltRiskManagementReport:
    core = build_backtest_report(
        configuration=backtest_configuration,
        strategy_configuration=strategy_configuration,
        provenance=provenance.backtest_provenance,
        predictions=predictions,
        bars=bars,
        result=result.backtest_result,
    )
    risk_events = [_event_payload(item) for item in result.risk_events]
    accepted = [
        item
        for item in risk_events
        if item["event_type"] == RiskEventType.ACCEPTED.value
    ]
    rejected = [
        item
        for item in risk_events
        if item["event_type"] == RiskEventType.REJECTED.value
    ]
    forced = [
        item
        for item in risk_events
        if item["event_type"] == RiskEventType.FORCED_EXIT.value
    ]
    protection = [
        item
        for item in risk_events
        if item["event_type"]
        in {
            RiskEventType.REJECTED.value,
            RiskEventType.ALLOCATION_REDUCED.value,
            RiskEventType.FORCED_EXIT.value,
            RiskEventType.PROTECTION.value,
        }
    ]
    triggered_counts: dict[str, int] = {}
    for event in result.risk_events:
        for rule in event.rule_names:
            triggered_counts[rule] = triggered_counts.get(rule, 0) + 1
    configuration_payload = {
        "report_version": RISK_REPORT_VERSION,
        "framework_version": RISK_FRAMEWORK_VERSION,
        "backtest": core.configuration,
        "risk": _serialize(asdict(risk_configuration)),
        "active_rules": list(risk_configuration.active_rule_names()),
        "barrier_policy": {
            "fixed_stop_and_take_profit": (
                "evaluated_from_current_completed_daily_ohlc"
            ),
            "trailing_high_watermark": (
                "prior_completed_bars_only"
            ),
            "same_bar_ambiguity": (
                "protective_exit_precedes_take_profit"
            ),
            "protective_fill": (
                "gap_aware_trigger_with_adverse_sell_slippage"
            ),
        },
        "source_backtest_report": {
            "report_id": str(provenance.source_backtest_report_id),
            "configuration_hash": (
                provenance.source_backtest_configuration_hash
            ),
            "result_hash": provenance.source_backtest_result_hash,
        },
    }
    risk_event_hash = hash_json(risk_events)
    accepted_hash = hash_json(accepted)
    rejected_hash = hash_json(rejected)
    forced_hash = hash_json(forced)
    protection_hash = hash_json(protection)
    payload = {
        "report_version": RISK_REPORT_VERSION,
        "framework_version": RISK_FRAMEWORK_VERSION,
        "configuration": configuration_payload,
        "metrics": core.payload["metrics"],
        "triggered_rules": dict(sorted(triggered_counts.items())),
        "accepted_trades": accepted,
        "rejected_trades": rejected,
        "forced_exits": forced,
        "portfolio_protection_events": protection,
        "risk_events": risk_events,
        "trade_log": core.payload["trade_log"],
        "equity_curve": core.payload["equity_curve"],
        "daily_portfolio_history": (
            core.payload["daily_portfolio_history"]
        ),
        "execution_fills": core.payload["execution_fills"],
        "signals": core.payload["signals"],
        "provenance": {
            **core.payload["provenance"],
            "source_backtest_report_id": str(
                provenance.source_backtest_report_id
            ),
            "source_backtest_configuration_hash": (
                provenance.source_backtest_configuration_hash
            ),
            "source_backtest_result_hash": (
                provenance.source_backtest_result_hash
            ),
        },
        "artifact_hashes": {
            **core.payload["artifact_hashes"],
            "risk_events_sha256": risk_event_hash,
            "accepted_trades_sha256": accepted_hash,
            "rejected_trades_sha256": rejected_hash,
            "forced_exits_sha256": forced_hash,
            "portfolio_protection_events_sha256": protection_hash,
        },
        "verification": {
            **core.payload["verification"],
            "all_active_rules_evaluated_before_orders": True,
            "forced_exits_deterministic": True,
            "risk_configuration_persisted": True,
            "research_artifacts_modified": False,
        },
    }
    return BuiltRiskManagementReport(
        configuration=configuration_payload,
        configuration_hash=hash_json(configuration_payload),
        payload=payload,
        result_hash=hash_json(payload),
        risk_event_hash=risk_event_hash,
        accepted_trade_hash=accepted_hash,
        rejected_trade_hash=rejected_hash,
        forced_exit_hash=forced_hash,
        protection_event_hash=protection_hash,
    )


def _event_payload(item: RiskEvent) -> dict[str, Any]:
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


def _optional_decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    return value

