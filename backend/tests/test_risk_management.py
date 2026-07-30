"""Independent and integrated deterministic risk management tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.backtesting.models import (
    BacktestConfig,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)
from app.backtesting.reporting import BacktestProvenance
from app.backtesting.risk.config import (
    AllocationMode,
    DailyLossLimitRule,
    MaximumAssetExposureRule,
    MaximumConcurrentPositionsRule,
    MaximumDrawdownRule,
    MaximumPortfolioExposureRule,
    MaximumPositionSizeRule,
    MinimumCashReserveRule,
    PositionSizingConfig,
    RiskConfiguration,
    StopLossRule,
    TakeProfitRule,
    TradingCooldownRule,
    TrailingStopRule,
)
from app.backtesting.risk.engine import run_risk_managed_backtest
from app.backtesting.risk.manager import RiskManager
from app.backtesting.risk.models import EntryRiskContext
from app.backtesting.risk.reporting import RiskReportProvenance
from app.backtesting.risk.rules import forced_exit_decision
from app.backtesting.risk.sizing import PositionSizer


class RiskManagementTests(unittest.TestCase):
    def test_percentage_fixed_and_fractional_position_sizing(self) -> None:
        percentage = PositionSizer(
            PositionSizingConfig(
                AllocationMode.PERCENTAGE,
                Decimal("0.25"),
                True,
            )
        )
        fixed = PositionSizer(
            PositionSizingConfig(
                AllocationMode.FIXED,
                Decimal("250"),
                False,
            )
        )

        self.assertEqual(
            percentage.requested_cash_allocation(Decimal("2000")),
            Decimal("500.00"),
        )
        self.assertEqual(
            fixed.requested_cash_allocation(Decimal("2000")),
            Decimal("250"),
        )
        self.assertTrue(percentage.allow_fractional_quantity)
        self.assertFalse(fixed.allow_fractional_quantity)

    def test_maximum_position_size_reduces_allocation(self) -> None:
        manager = _manager(
            maximum_position_size=MaximumPositionSizeRule(
                Decimal("0.2"),
                Decimal("150"),
            )
        )

        decision = manager.evaluate_entry(_context())

        self.assertTrue(decision.permitted)
        self.assertEqual(decision.approved_cash_allocation, Decimal("150"))
        self.assertEqual(
            decision.triggered_rules,
            (
                "maximum_position_size_fraction",
                "maximum_position_size_fixed",
            ),
        )

    def test_portfolio_and_asset_exposure_limits_are_independent(self) -> None:
        portfolio = _manager(
            maximum_portfolio_exposure=(
                MaximumPortfolioExposureRule(Decimal("0.6"))
            )
        ).evaluate_entry(
            replace(
                _context(),
                current_portfolio_exposure=Decimal("500"),
            )
        )
        asset = _manager(
            maximum_asset_exposure=MaximumAssetExposureRule(
                Decimal("0.3")
            )
        ).evaluate_entry(
            replace(
                _context(),
                current_asset_exposure=Decimal("250"),
            )
        )

        self.assertEqual(
            portfolio.approved_cash_allocation,
            Decimal("100.0"),
        )
        self.assertEqual(
            portfolio.triggered_rules,
            ("maximum_portfolio_exposure",),
        )
        self.assertEqual(asset.approved_cash_allocation, Decimal("50.0"))
        self.assertEqual(
            asset.triggered_rules,
            ("maximum_asset_exposure",),
        )

    def test_maximum_concurrent_positions_rejects_entry(self) -> None:
        manager = _manager(
            maximum_concurrent_positions=(
                MaximumConcurrentPositionsRule(1)
            )
        )

        decision = manager.evaluate_entry(
            replace(_context(), open_position_count=1)
        )

        self.assertFalse(decision.permitted)
        self.assertEqual(
            decision.rejection_reasons,
            ("maximum_concurrent_positions",),
        )

    def test_minimum_cash_reserve_caps_or_rejects_entry(self) -> None:
        manager = _manager(
            minimum_cash_reserve=MinimumCashReserveRule(
                Decimal("800")
            )
        )

        capped = manager.evaluate_entry(_context())
        rejected = manager.evaluate_entry(
            replace(_context(), cash=Decimal("800"))
        )

        self.assertEqual(capped.approved_cash_allocation, Decimal("200"))
        self.assertIn("minimum_cash_reserve", capped.triggered_rules)
        self.assertFalse(rejected.permitted)
        self.assertIn(
            "minimum_cash_reserve",
            rejected.rejection_reasons,
        )

    def test_cooldown_rejects_configured_observations_after_exit(self) -> None:
        manager = _manager(
            trading_cooldown=TradingCooldownRule(2)
        )
        manager.record_exit(3)

        blocked = manager.evaluate_entry(
            replace(_context(), observation_index=5)
        )
        permitted = manager.evaluate_entry(
            replace(_context(), observation_index=6)
        )

        self.assertFalse(blocked.permitted)
        self.assertEqual(
            blocked.rejection_reasons,
            ("trading_cooldown",),
        )
        self.assertTrue(permitted.permitted)

    def test_daily_loss_and_drawdown_block_new_entries(self) -> None:
        manager = _manager(
            daily_loss_limit=DailyLossLimitRule(Decimal("0.05")),
            maximum_drawdown=MaximumDrawdownRule(Decimal("0.1")),
        )
        context = replace(
            _context(),
            portfolio_equity=Decimal("850"),
            previous_close_equity=Decimal("900"),
            portfolio_peak=Decimal("1000"),
        )

        decision = manager.evaluate_entry(context)

        self.assertFalse(decision.permitted)
        self.assertEqual(
            decision.rejection_reasons,
            ("daily_loss_limit", "maximum_drawdown"),
        )

    def test_stop_loss_rule_forces_exit(self) -> None:
        decision = forced_exit_decision(
            configuration=_risk(
                stop_loss=StopLossRule(Decimal("0.1"))
            ),
            bar=_bar(1, "100", "105", "89", "95"),
            entry_price=Decimal("100"),
            quantity=Decimal("5"),
            prior_high_watermark=Decimal("100"),
            cash=Decimal("500"),
            portfolio_peak=Decimal("1000"),
            previous_close_equity=Decimal("1000"),
        )

        self.assertTrue(decision.required)
        self.assertEqual(decision.triggered_rules, ("stop_loss",))
        self.assertEqual(decision.reference_price, Decimal("90.0"))

    def test_take_profit_rule_forces_exit(self) -> None:
        decision = forced_exit_decision(
            configuration=_risk(
                take_profit=TakeProfitRule(Decimal("0.1"))
            ),
            bar=_bar(1, "100", "111", "99", "108"),
            entry_price=Decimal("100"),
            quantity=Decimal("5"),
            prior_high_watermark=Decimal("100"),
            cash=Decimal("500"),
            portfolio_peak=Decimal("1000"),
            previous_close_equity=Decimal("1000"),
        )

        self.assertTrue(decision.required)
        self.assertEqual(decision.triggered_rules, ("take_profit",))
        self.assertEqual(decision.reference_price, Decimal("110.0"))

    def test_trailing_stop_uses_only_prior_completed_high(self) -> None:
        decision = forced_exit_decision(
            configuration=_risk(
                trailing_stop=TrailingStopRule(Decimal("0.1"))
            ),
            bar=_bar(1, "115", "200", "107", "150"),
            entry_price=Decimal("100"),
            quantity=Decimal("5"),
            prior_high_watermark=Decimal("120"),
            cash=Decimal("500"),
            portfolio_peak=Decimal("1100"),
            previous_close_equity=Decimal("1100"),
        )

        self.assertTrue(decision.required)
        self.assertEqual(decision.triggered_rules, ("trailing_stop",))
        self.assertEqual(decision.reference_price, Decimal("108.0"))

    def test_daily_loss_and_drawdown_force_protective_exit(self) -> None:
        decision = forced_exit_decision(
            configuration=_risk(
                daily_loss_limit=DailyLossLimitRule(Decimal("0.05")),
                maximum_drawdown=MaximumDrawdownRule(Decimal("0.1")),
            ),
            bar=_bar(1, "100", "101", "79", "80"),
            entry_price=Decimal("100"),
            quantity=Decimal("5"),
            prior_high_watermark=Decimal("100"),
            cash=Decimal("500"),
            portfolio_peak=Decimal("1000"),
            previous_close_equity=Decimal("1000"),
        )

        self.assertTrue(decision.required)
        self.assertEqual(
            decision.triggered_rules,
            ("daily_loss_limit", "maximum_drawdown"),
        )
        self.assertEqual(decision.reference_price, Decimal("80.0"))

    def test_protective_exit_precedes_same_bar_take_profit(self) -> None:
        decision = forced_exit_decision(
            configuration=_risk(
                stop_loss=StopLossRule(Decimal("0.1")),
                take_profit=TakeProfitRule(Decimal("0.1")),
            ),
            bar=_bar(1, "100", "120", "85", "105"),
            entry_price=Decimal("100"),
            quantity=Decimal("5"),
            prior_high_watermark=Decimal("100"),
            cash=Decimal("500"),
            portfolio_peak=Decimal("1000"),
            previous_close_equity=Decimal("1000"),
        )

        self.assertEqual(decision.triggered_rules, ("stop_loss",))
        self.assertEqual(decision.reference_price, Decimal("90.0"))

    def test_forced_exit_cooldown_and_rejection_are_audited(self) -> None:
        execution = run_risk_managed_backtest(
            predictions=_predictions(Decimal("0.01"), Decimal("0.01")),
            bars=(
                _bar(0, "100", "101", "99", "100"),
                _bar(1, "100", "105", "85", "90"),
                _bar(2, "90", "95", "89", "92"),
            ),
            backtest_configuration=_backtest(),
            strategy_configuration=_strategy(),
            risk_configuration=_risk(
                stop_loss=StopLossRule(Decimal("0.1")),
                trading_cooldown=TradingCooldownRule(2),
            ),
            provenance=_provenance(),
        )
        events = execution.result.risk_events

        self.assertEqual(
            [item.reason for item in events],
            [
                "buy_accepted",
                "risk_forced_exit:stop_loss",
                "buy_rejected",
            ],
        )
        self.assertEqual(
            execution.report.payload["triggered_rules"],
            {"stop_loss": 1, "trading_cooldown": 1},
        )
        self.assertEqual(
            len(execution.report.payload["forced_exits"]),
            1,
        )
        self.assertEqual(
            len(execution.report.payload["rejected_trades"]),
            1,
        )

    def test_combined_report_is_exactly_repeatable(self) -> None:
        inputs = {
            "predictions": _predictions(
                Decimal("0.01"),
                Decimal("0.01"),
            ),
            "bars": (
                _bar(0, "100", "101", "99", "100"),
                _bar(1, "100", "105", "85", "90"),
                _bar(2, "90", "95", "89", "92"),
            ),
            "backtest_configuration": _backtest(),
            "strategy_configuration": _strategy(),
            "risk_configuration": _risk(
                stop_loss=StopLossRule(Decimal("0.1")),
                take_profit=TakeProfitRule(Decimal("0.2")),
                minimum_cash_reserve=MinimumCashReserveRule(
                    Decimal("100")
                ),
            ),
            "provenance": _provenance(),
        }

        first = run_risk_managed_backtest(**inputs)
        second = run_risk_managed_backtest(**inputs)

        self.assertEqual(
            first.report.configuration_hash,
            second.report.configuration_hash,
        )
        self.assertEqual(first.report.result_hash, second.report.result_hash)
        self.assertEqual(
            first.report.risk_event_hash,
            second.report.risk_event_hash,
        )


def _manager(**overrides) -> RiskManager:
    return RiskManager(_risk(**overrides), Decimal("1000"))


def _risk(**overrides) -> RiskConfiguration:
    values = {
        "position_sizing": PositionSizingConfig(
            AllocationMode.PERCENTAGE,
            Decimal("0.5"),
            True,
        ),
        "maximum_position_size": None,
        "maximum_portfolio_exposure": None,
        "maximum_asset_exposure": None,
        "maximum_concurrent_positions": None,
        "stop_loss": None,
        "take_profit": None,
        "trailing_stop": None,
        "daily_loss_limit": None,
        "maximum_drawdown": None,
        "minimum_cash_reserve": None,
        "trading_cooldown": None,
    }
    values.update(overrides)
    return RiskConfiguration(**values)


def _context() -> EntryRiskContext:
    return EntryRiskContext(
        timestamp=_start(),
        observation_index=0,
        cash=Decimal("1000"),
        portfolio_equity=Decimal("1000"),
        current_portfolio_exposure=Decimal("0"),
        current_asset_exposure=Decimal("0"),
        open_position_count=0,
        portfolio_peak=Decimal("1000"),
        previous_close_equity=Decimal("1000"),
        last_exit_observation_index=None,
    )


def _backtest() -> BacktestConfig:
    return BacktestConfig(
        initial_capital=Decimal("1000"),
        position_size_fraction=Decimal("0.5"),
        long_only=True,
        transaction_cost_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        maximum_concurrent_positions=1,
        daily_position_updates=True,
        liquidate_at_end=True,
        annualization_periods=252,
        annual_risk_free_rate=Decimal("0"),
    )


def _strategy() -> StrategyConfig:
    return StrategyConfig(
        "ridge_threshold_long_only",
        "1.0.0",
        Decimal("0"),
        Decimal("0"),
    )


def _start() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bar(
    day: int,
    open_price: str,
    high_price: str,
    low_price: str,
    close_price: str,
) -> MarketBar:
    return MarketBar(
        timestamp=_start() + timedelta(days=day),
        open_price=Decimal(open_price),
        high_price=Decimal(high_price),
        low_price=Decimal(low_price),
        close_price=Decimal(close_price),
    )


def _predictions(*values: Decimal) -> tuple[PredictionPoint, ...]:
    return tuple(
        PredictionPoint(
            prediction_timestamp=_start() + timedelta(days=index),
            predicted_forward_return=value,
            evidence_hash=f"{index + 1:064x}",
        )
        for index, value in enumerate(values)
    )


def _provenance() -> RiskReportProvenance:
    return RiskReportProvenance(
        backtest_provenance=BacktestProvenance(
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
        ),
        source_backtest_report_id=UUID(int=5),
        source_backtest_configuration_hash="2" * 64,
        source_backtest_result_hash="3" * 64,
    )
