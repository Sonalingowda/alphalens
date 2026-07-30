"""Verified read-only projection of immutable dashboard evidence."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.artifact import hash_json
from app.inference.repository import load_production_artifact
from app.persistence.models import (
    BacktestReportRecord,
    PaperTradingReportRecord,
    RiskManagementReportRecord,
)


async def load_dashboard_snapshot(
    session: AsyncSession,
) -> dict[str, Any]:
    artifact = await load_production_artifact(session)
    paper = (
        await session.scalars(
            select(PaperTradingReportRecord)
            .order_by(PaperTradingReportRecord.cycle_end.desc())
            .limit(1)
        )
    ).one_or_none()
    backtests = tuple(
        (
            await session.scalars(
                select(BacktestReportRecord).order_by(
                    BacktestReportRecord.generated_at.desc()
                )
            )
        ).all()
    )
    risk = (
        await session.scalars(
            select(RiskManagementReportRecord)
            .order_by(RiskManagementReportRecord.generated_at.desc())
            .limit(1)
        )
    ).one_or_none()
    if paper is not None:
        _verify_report(
            paper.report_configuration,
            paper.configuration_hash,
            paper.report_payload,
            paper.result_hash,
            "paper trading",
        )
    for item in backtests:
        _verify_report(
            item.report_configuration,
            item.configuration_hash,
            item.report_payload,
            item.result_hash,
            "backtest",
        )
    if risk is not None:
        _verify_report(
            risk.report_configuration,
            risk.configuration_hash,
            risk.report_payload,
            risk.result_hash,
            "risk management",
        )
    return {
        "snapshot_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prediction": _latest_prediction(paper),
        "signal": _latest_item(paper, "signals"),
        "confidence": {
            "available": False,
            "reason": (
                "The approved Ridge regression artifact does not "
                "produce calibrated confidence estimates."
            ),
        },
        "portfolio": _portfolio_summary(paper),
        "predictions": _payload_list(paper, "predictions"),
        "signals": _payload_list(paper, "signals"),
        "orders": _payload_list(paper, "orders"),
        "trades": _payload_list(paper, "trades"),
        "risk_events": _risk_events(risk),
        "portfolio_history": _payload_list(
            paper,
            "portfolio_history",
        ),
        "charts": _chart_payload(paper),
        "backtest_reports": [
            {
                "report_id": str(item.id),
                "report_version": item.report_version,
                "engine_version": item.engine_version,
                "generated_at": item.generated_at.isoformat(),
                "period_start": item.period_start.isoformat(),
                "period_end": item.period_end.isoformat(),
                "metrics": item.report_payload["metrics"],
                "equity_curve": item.report_payload["equity_curve"],
                "trade_log": item.report_payload["trade_log"],
                "signals": item.report_payload["signals"],
                "result_hash": item.result_hash,
                "configuration_hash": item.configuration_hash,
            }
            for item in backtests
        ],
        "system": {
            "api_version": "1.0.0",
            "database_status": "connected",
            "model_family": artifact.model_family,
            "model_version": "1.0.0",
            "artifact_identifier": str(artifact.artifact_id),
            "artifact_sha256": artifact.artifact_sha256,
            "artifact_configuration_hash": (
                artifact.configuration_hash
            ),
            "feature_pipeline_version": (
                artifact.feature_pipeline_version
            ),
            "target_version": artifact.target_version,
            "paper_engine_version": (
                paper.engine_version if paper is not None else None
            ),
            "risk_framework_version": (
                risk.framework_version if risk is not None else None
            ),
            "test_status": "not_published_by_runtime",
        },
        "settings": _settings(paper),
        "provenance": {
            "paper_report_id": str(paper.id) if paper else None,
            "paper_result_hash": paper.result_hash if paper else None,
            "risk_report_id": str(risk.id) if risk else None,
            "risk_result_hash": risk.result_hash if risk else None,
            "backtest_report_ids": [
                str(item.id) for item in backtests
            ],
            "inference_artifact_id": str(artifact.artifact_id),
        },
    }


def _verify_report(
    configuration: dict,
    configuration_hash: str,
    payload: dict,
    result_hash: str,
    name: str,
) -> None:
    if (
        hash_json(configuration) != configuration_hash
        or hash_json(payload) != result_hash
    ):
        raise ValueError(f"Immutable {name} report hash differs.")


def _latest_prediction(
    paper: PaperTradingReportRecord | None,
) -> dict[str, Any] | None:
    prediction = _latest_item(paper, "predictions")
    if prediction is None:
        return None
    return {
        **prediction,
        "target_name": "forward_log_return",
        "target_version": (
            paper.target_version if paper is not None else None
        ),
        "horizon_observations": 5,
    }


def _latest_item(
    paper: PaperTradingReportRecord | None,
    key: str,
) -> dict[str, Any] | None:
    values = _payload_list(paper, key)
    return values[-1] if values else None


def _payload_list(
    paper: PaperTradingReportRecord | None,
    key: str,
) -> list[dict[str, Any]]:
    if paper is None:
        return []
    values = paper.report_payload.get(key, [])
    return values if isinstance(values, list) else []


def _portfolio_summary(
    paper: PaperTradingReportRecord | None,
) -> dict[str, Any]:
    if paper is None:
        return {
            "available": False,
            "cash": None,
            "portfolio_value": None,
            "daily_pnl": None,
            "unrealized_pnl": None,
            "realized_pnl": None,
            "open_position_count": 0,
            "closed_trade_count": 0,
        }
    payload = paper.report_payload
    history = payload["portfolio_history"]
    current = history[-1]
    previous = history[-2] if len(history) > 1 else None
    daily_pnl = (
        Decimal(current["portfolio_value"])
        - Decimal(previous["portfolio_value"])
        if previous is not None
        else None
    )
    trades = payload["trades"]
    realized = sum(
        (Decimal(item["net_profit_loss"]) for item in trades),
        Decimal("0"),
    )
    position = payload["state"]["open_position"]
    unrealized = None
    if position is not None:
        quantity = Decimal(
            position["entry_fill"]["quantity"]
        )
        entry_price = Decimal(
            position["entry_fill"]["execution_price"]
        )
        market_value = Decimal(current["position_market_value"])
        unrealized = market_value - quantity * entry_price
    return {
        "available": True,
        "cash": current["cash"],
        "portfolio_value": current["portfolio_value"],
        "daily_pnl": _optional_decimal(daily_pnl),
        "unrealized_pnl": _optional_decimal(unrealized),
        "realized_pnl": format(realized, "f"),
        "open_position_count": current["open_position_count"],
        "closed_trade_count": len(trades),
    }


def _risk_events(
    risk: RiskManagementReportRecord | None,
) -> list[dict[str, Any]]:
    if risk is None:
        return []
    return [
        {
            **item,
            "source": "risk_management_report",
            "report_id": str(risk.id),
        }
        for item in risk.report_payload["risk_events"]
    ]


def _chart_payload(
    paper: PaperTradingReportRecord | None,
) -> dict[str, list[dict[str, Any]]]:
    history = _payload_list(paper, "portfolio_history")
    predictions = _payload_list(paper, "predictions")
    trades = _payload_list(paper, "trades")
    peak: Decimal | None = None
    drawdown: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    for item in history:
        value = Decimal(item["portfolio_value"])
        peak = value if peak is None else max(peak, value)
        drawdown.append(
            {
                "timestamp": item["timestamp"],
                "value": format(value / peak - Decimal("1"), "f"),
            }
        )
        positions.append(
            {
                "timestamp": item["timestamp"],
                "value": item["position_market_value"],
            }
        )
    return {
        "equity_curve": [
            {
                "timestamp": item["timestamp"],
                "value": item["portfolio_value"],
            }
            for item in history
        ],
        "daily_returns": [
            {
                "timestamp": item["timestamp"],
                "value": item["daily_return"],
            }
            for item in history
        ],
        "drawdown": drawdown,
        "prediction_history": [
            {
                "timestamp": item["prediction_timestamp"],
                "value": item["predicted_forward_return"],
            }
            for item in predictions
        ],
        "trade_timeline": [
            {
                "timestamp": item["exit_timestamp"],
                "value": item["net_profit_loss"],
            }
            for item in trades
        ],
        "position_history": positions,
    }


def _settings(
    paper: PaperTradingReportRecord | None,
) -> dict[str, Any] | None:
    if paper is None:
        return None
    session = paper.report_configuration["paper_session"]
    return {
        "read_only": True,
        "session_name": session["session_name"],
        "asset_identifier": session["asset_identifier"],
        "quote_currency": session["quote_currency"],
        "timeframe": session["timeframe"],
        "execution_interval_seconds": (
            session["execution_interval_seconds"]
        ),
        "market_history_observations": (
            session["market_history_observations"]
        ),
        "strategy": session["strategy"],
        "risk": session["risk"],
        "portfolio": session["backtest"],
    }


def _optional_decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None

