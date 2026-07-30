"""Deterministic artifact-only paper trading cycle orchestration."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.backtesting.models import MarketBar, PredictionPoint
from app.backtesting.strategy import RidgeThresholdLongOnlyStrategy
from app.market_data.models import Candle
from app.paper_trading.audit import PaperAuditLogger, hash_lines
from app.paper_trading.features import PaperFeatureGenerationService
from app.paper_trading.inference import PaperInferenceService
from app.paper_trading.models import (
    PaperCycleResult,
    PaperMarketSnapshot,
    PaperTradingConfiguration,
    PaperTradingState,
)
from app.paper_trading.portfolio import PaperPortfolioManager


class PaperTradingEngine:
    def __init__(self) -> None:
        self._features = PaperFeatureGenerationService()
        self._portfolio = PaperPortfolioManager()
        self._audit = PaperAuditLogger()

    def run_cycle(
        self,
        *,
        snapshot: PaperMarketSnapshot,
        prior_state: PaperTradingState,
        configuration: PaperTradingConfiguration,
        inference: PaperInferenceService,
    ) -> PaperCycleResult | None:
        _validate_snapshot(snapshot, configuration)
        new_candles = _new_candles(snapshot.candles, prior_state)
        if not new_candles:
            return None
        timestamps = tuple(
            _required_timestamp(item) for item in new_candles
        )
        vectors = self._features.generate(
            candles=snapshot.candles,
            prediction_timestamps=timestamps,
            ordered_feature_names=inference.ordered_feature_names,
        )
        strategy = RidgeThresholdLongOnlyStrategy(
            configuration.strategy
        )
        state = prior_state
        cycle_prediction_hashes: list[str] = []
        for candle, vector in zip(
            new_candles,
            vectors,
            strict=True,
        ):
            bar = _market_bar(candle)
            audit = self._audit.append(
                state.audit_log,
                observation_timestamp=bar.timestamp,
                event_type="market_data_ingested",
                evidence={
                    "market_data_hash": snapshot.market_data_hash,
                    "completed_through": (
                        snapshot.completed_through.isoformat()
                    ),
                },
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="features_generated",
                evidence={
                    "pipeline_version": vector.pipeline_version,
                    "feature_vector_hash": vector.feature_vector_hash,
                },
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="inference_artifact_loaded",
                evidence={
                    "artifact_sha256": inference.artifact_sha256,
                    "fit_invoked": False,
                },
            )
            outcome = self._portfolio.advance(
                state=state,
                bar=bar,
                configuration=configuration,
            )
            prediction = inference.predict(vector)
            cycle_prediction_hashes.append(prediction.evidence_hash)
            signal = strategy.generate_signal(
                PredictionPoint(
                    prediction_timestamp=(
                        prediction.prediction_timestamp
                    ),
                    predicted_forward_return=(
                        prediction.predicted_forward_return
                    ),
                    evidence_hash=prediction.evidence_hash,
                )
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="prediction_generated",
                evidence={
                    "prediction_evidence_hash": (
                        prediction.evidence_hash
                    ),
                    "predicted_float_hex": (
                        prediction.predicted_float_hex
                    ),
                    "artifact_sha256": (
                        prediction.inference_artifact_sha256
                    ),
                },
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="signal_generated",
                evidence={
                    "action": signal.action.value,
                    "source_prediction_hash": (
                        signal.source_prediction_hash
                    ),
                },
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="risk_evaluated",
                evidence={
                    "active_rules": list(
                        configuration.risk.active_rule_names()
                    ),
                    "cycle_risk_event_count": len(
                        outcome.risk_events
                    ),
                },
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="paper_orders_executed",
                evidence={
                    "cycle_fill_count": len(outcome.fills),
                    "live_order_placed": False,
                },
            )
            audit = self._audit.append(
                audit,
                observation_timestamp=bar.timestamp,
                event_type="portfolio_updated",
                evidence={
                    "cash": format(outcome.cash, "f"),
                    "portfolio_value": format(
                        outcome.snapshot.portfolio_value,
                        "f",
                    ),
                    "open_position_count": (
                        outcome.snapshot.open_position_count
                    ),
                },
            )
            state = replace(
                state,
                observation_sequence=state.observation_sequence + 1,
                last_market_timestamp=bar.timestamp,
                cash=outcome.cash,
                open_position=outcome.open_position,
                pending_signal=signal,
                portfolio_peak=outcome.portfolio_peak,
                previous_close_equity=(
                    outcome.previous_close_equity
                ),
                last_exit_observation_index=(
                    outcome.last_exit_observation_index
                ),
                predictions=(*state.predictions, prediction),
                signals=(*state.signals, signal),
                fills=(*state.fills, *outcome.fills),
                closed_trades=(
                    *state.closed_trades,
                    *outcome.closed_trades,
                ),
                risk_events=(
                    *state.risk_events,
                    *outcome.risk_events,
                ),
                portfolio_history=(
                    *state.portfolio_history,
                    outcome.snapshot,
                ),
                audit_log=audit,
            )
        return PaperCycleResult(
            state=state,
            processed_observation_count=len(new_candles),
            cycle_start=timestamps[0],
            cycle_end=timestamps[-1],
            market_data_hash=snapshot.market_data_hash,
            feature_set_hash=hash_lines(
                tuple(item.feature_vector_hash for item in vectors)
            ),
            prediction_set_hash=hash_lines(
                tuple(cycle_prediction_hashes)
            ),
        )


def _new_candles(
    candles: tuple[Candle, ...],
    state: PaperTradingState,
) -> tuple[Candle, ...]:
    if state.last_market_timestamp is None:
        return candles[-1:]
    new = tuple(
        item
        for item in candles
        if _required_timestamp(item) > state.last_market_timestamp
    )
    if (
        new
        and _required_timestamp(new[0])
        != state.last_market_timestamp + timedelta(days=1)
    ):
        raise ValueError(
            "Paper engine cannot skip an unobserved execution candle."
        )
    return new


def _validate_snapshot(
    snapshot: PaperMarketSnapshot,
    configuration: PaperTradingConfiguration,
) -> None:
    if (
        snapshot.asset_identifier != configuration.asset_identifier
        or snapshot.quote_currency != configuration.quote_currency
        or snapshot.timeframe != configuration.timeframe
        or not snapshot.candles
        or len(snapshot.market_data_hash) != 64
        or _required_timestamp(snapshot.candles[-1])
        != snapshot.completed_through
    ):
        raise ValueError("Paper market snapshot differs from configuration.")


def _market_bar(candle: Candle) -> MarketBar:
    timestamp = _required_timestamp(candle)
    values = (candle.open, candle.high, candle.low, candle.close)
    if any(item is None for item in values):
        raise ValueError("Paper candle contains missing OHLC fields.")
    return MarketBar(
        timestamp=timestamp,
        open_price=_required_decimal(candle.open),
        high_price=_required_decimal(candle.high),
        low_price=_required_decimal(candle.low),
        close_price=_required_decimal(candle.close),
    )


def _required_timestamp(candle: Candle):
    if candle.timestamp is None:
        raise ValueError("Paper candle timestamp is missing.")
    return candle.timestamp


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise ValueError("Paper candle price is missing.")
    return value
