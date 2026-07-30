"""Comprehensive deterministic backtesting engine tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.backtesting.engine import run_backtest
from app.backtesting.execution import OrderExecutionSimulator
from app.backtesting.metrics import calculate_performance_metrics
from app.backtesting.models import (
    BacktestConfig,
    MarketBar,
    PredictionPoint,
    SignalAction,
    StrategyConfig,
)
from app.backtesting.portfolio import simulate_portfolio
from app.backtesting.reporting import BacktestProvenance
from app.backtesting.signals import generate_signals
from app.backtesting.strategy import RidgeThresholdLongOnlyStrategy


class BacktestingTests(unittest.TestCase):
    def test_signal_generation_supports_buy_hold_and_exit(self) -> None:
        predictions = _predictions(
            Decimal("0.01"),
            Decimal("0"),
            Decimal("-0.01"),
        )

        signals = generate_signals(
            predictions,
            RidgeThresholdLongOnlyStrategy(_strategy()),
        )

        self.assertEqual(
            tuple(item.action for item in signals),
            (
                SignalAction.BUY,
                SignalAction.HOLD,
                SignalAction.EXIT,
            ),
        )
        self.assertEqual(
            tuple(item.source_prediction_hash for item in signals),
            tuple(item.evidence_hash for item in predictions),
        )

    def test_execution_applies_configured_costs_and_slippage(self) -> None:
        simulator = OrderExecutionSimulator(
            _configuration(
                transaction_cost_bps=Decimal("10"),
                slippage_bps=Decimal("5"),
            )
        )
        timestamp = _start()

        buy = simulator.execute_buy(
            signal_timestamp=timestamp,
            execution_timestamp=timestamp + timedelta(days=1),
            reference_price=Decimal("100"),
            available_cash=Decimal("1000"),
        )
        sell = simulator.execute_sell(
            signal_timestamp=timestamp + timedelta(days=2),
            execution_timestamp=timestamp + timedelta(days=3),
            reference_price=Decimal("110"),
            quantity=buy.quantity,
            reason="strategy_exit_next_open",
        )

        self.assertEqual(buy.execution_price, Decimal("100.0500"))
        self.assertEqual(buy.cash_delta, Decimal("-500.0"))
        self.assertEqual(sell.execution_price, Decimal("109.9450"))
        self.assertGreater(sell.transaction_cost, Decimal("0"))
        self.assertLess(sell.cash_delta, sell.gross_notional)

    def test_portfolio_executes_only_at_next_observation_open(self) -> None:
        bars = _bars(
            ("100", "100"),
            ("100", "110"),
            ("110", "120"),
            ("120", "120"),
        )
        predictions = _predictions(
            Decimal("0.01"),
            Decimal("0"),
            Decimal("-0.01"),
        )
        signals = generate_signals(
            predictions,
            RidgeThresholdLongOnlyStrategy(_strategy()),
        )

        result = simulate_portfolio(
            bars=bars,
            signals=signals,
            configuration=_configuration(),
        )

        self.assertEqual(len(result.fills), 2)
        self.assertEqual(
            result.fills[0].execution_timestamp,
            bars[1].timestamp,
        )
        self.assertEqual(
            result.fills[1].execution_timestamp,
            bars[3].timestamp,
        )
        self.assertEqual(result.final_portfolio_value, Decimal("1100.0"))
        self.assertEqual(result.closed_trades[0].net_profit_loss, Decimal("100.0"))
        self.assertEqual(result.daily_history[0].daily_return, Decimal("0"))

    def test_terminal_liquidation_is_distinct_from_strategy_exit(self) -> None:
        bars = _bars(
            ("100", "100"),
            ("100", "105"),
            ("105", "110"),
        )
        signals = generate_signals(
            _predictions(Decimal("0.01"), Decimal("0.01")),
            RidgeThresholdLongOnlyStrategy(_strategy()),
        )

        result = simulate_portfolio(
            bars=bars,
            signals=signals,
            configuration=_configuration(),
        )

        self.assertEqual(len(result.closed_trades), 1)
        self.assertEqual(
            result.closed_trades[0].exit_reason,
            "terminal_liquidation_at_close",
        )
        self.assertIsNone(result.closed_trades[0].exit_signal_timestamp)

    def test_performance_metrics_match_known_accounting(self) -> None:
        bars = _bars(
            ("100", "100"),
            ("100", "110"),
            ("110", "120"),
            ("120", "120"),
        )
        signals = generate_signals(
            _predictions(
                Decimal("0.01"),
                Decimal("0"),
                Decimal("-0.01"),
            ),
            RidgeThresholdLongOnlyStrategy(_strategy()),
        )
        configuration = _configuration()
        result = simulate_portfolio(
            bars=bars,
            signals=signals,
            configuration=configuration,
        )

        metrics = calculate_performance_metrics(result, configuration)

        self.assertEqual(metrics["total_return"], Decimal("0.1"))
        self.assertEqual(metrics["maximum_drawdown"], Decimal("0"))
        self.assertEqual(metrics["win_rate"], Decimal("1"))
        self.assertEqual(metrics["average_gain"], Decimal("100.0"))
        self.assertIsNone(metrics["average_loss"])
        self.assertIsNone(metrics["profit_factor"])
        self.assertEqual(metrics["number_of_trades"], 1)

    def test_report_and_artifact_hashes_are_repeatable(self) -> None:
        inputs = {
            "predictions": _predictions(
                Decimal("0.01"),
                Decimal("0"),
                Decimal("-0.01"),
            ),
            "bars": _bars(
                ("100", "100"),
                ("100", "110"),
                ("110", "120"),
                ("120", "120"),
            ),
            "configuration": _configuration(),
            "strategy_configuration": _strategy(),
            "provenance": _provenance(),
        }

        first = run_backtest(**inputs)
        second = run_backtest(**inputs)

        self.assertEqual(
            first.report.configuration_hash,
            second.report.configuration_hash,
        )
        self.assertEqual(first.report.result_hash, second.report.result_hash)
        self.assertEqual(
            first.report.input_evidence_hash,
            second.report.input_evidence_hash,
        )
        self.assertEqual(
            first.report.trade_log_hash,
            second.report.trade_log_hash,
        )
        self.assertFalse(
            first.report.payload["verification"][
                "research_artifacts_modified"
            ]
        )
        self.assertFalse(
            first.report.payload["verification"]["model_retrained"]
        )

    def test_invalid_or_non_chronological_inputs_are_rejected(self) -> None:
        predictions = tuple(reversed(_predictions(Decimal("0.01"), Decimal("0"))))

        with self.assertRaisesRegex(ValueError, "chronological"):
            generate_signals(
                predictions,
                RidgeThresholdLongOnlyStrategy(_strategy()),
            )


def _configuration(
    *,
    transaction_cost_bps: Decimal = Decimal("0"),
    slippage_bps: Decimal = Decimal("0"),
) -> BacktestConfig:
    return BacktestConfig(
        initial_capital=Decimal("1000"),
        position_size_fraction=Decimal("0.5"),
        long_only=True,
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        maximum_concurrent_positions=1,
        daily_position_updates=True,
        liquidate_at_end=True,
        annualization_periods=252,
        annual_risk_free_rate=Decimal("0"),
    )


def _strategy() -> StrategyConfig:
    return StrategyConfig(
        strategy_name="ridge_threshold_long_only",
        strategy_version="1.0.0",
        buy_threshold=Decimal("0"),
        exit_threshold=Decimal("0"),
    )


def _start() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _predictions(*values: Decimal) -> tuple[PredictionPoint, ...]:
    return tuple(
        PredictionPoint(
            prediction_timestamp=_start() + timedelta(days=index),
            predicted_forward_return=value,
            evidence_hash=f"{index + 1:064x}",
        )
        for index, value in enumerate(values)
    )


def _bars(
    *values: tuple[str, str],
) -> tuple[MarketBar, ...]:
    return tuple(
        MarketBar(
            timestamp=_start() + timedelta(days=index),
            open_price=Decimal(open_price),
            high_price=max(Decimal(open_price), Decimal(close_price)),
            low_price=min(Decimal(open_price), Decimal(close_price)),
            close_price=Decimal(close_price),
        )
        for index, (open_price, close_price) in enumerate(values)
    )


def _provenance() -> BacktestProvenance:
    return BacktestProvenance(
        holdout_evaluation_report_id=UUID(int=1),
        holdout_configuration_hash="a" * 64,
        holdout_result_hash="b" * 64,
        selected_experiment_id=UUID(int=2),
        selected_experiment_configuration_hash="c" * 64,
        selected_experiment_result_hash="d" * 64,
        model_dataset_hash="e" * 64,
        feature_pipeline_version="1.1.0",
        target_version="1.0.0",
        validation_run_id=UUID(int=3),
        split_hash="f" * 64,
        prediction_evidence_set_hash="1" * 64,
        candle_ingestion_batch_ids=(UUID(int=4),),
    )
