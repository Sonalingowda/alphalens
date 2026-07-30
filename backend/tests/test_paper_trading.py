"""Tests for deterministic artifact-only paper trading."""

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import inspect
from pathlib import Path
import unittest
from uuid import UUID

import numpy as np

from app.backtesting.models import BacktestConfig, StrategyConfig
from app.backtesting.risk.config import (
    AllocationMode,
    MaximumAssetExposureRule,
    MaximumConcurrentPositionsRule,
    MaximumPortfolioExposureRule,
    MaximumPositionSizeRule,
    MinimumCashReserveRule,
    PositionSizingConfig,
    RiskConfiguration,
    StopLossRule,
)
from app.inference.artifact import PackagedRidgeInference
from app.inference.repository import LoadedProductionArtifact
from app.inference.service import ProductionPredictionService
from app.market_data.models import (
    Candle,
    HistoricalCandlePage,
)
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.features import PaperFeatureGenerationService
from app.paper_trading.inference import PaperInferenceService
from app.paper_trading.market_data import KrakenPaperMarketDataService
from app.paper_trading.models import (
    PaperMarketSnapshot,
    PaperTradingConfiguration,
    PaperTradingProvenance,
    PaperTradingState,
)
from app.paper_trading.reporting import (
    build_paper_trading_report,
    state_from_report,
)
from app.paper_trading.scheduler import PredictionScheduler
from app.research.dataset import MODEL_FEATURE_NAMES


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class PaperTradingTests(unittest.TestCase):
    def test_feature_generation_is_complete_and_point_in_time(self) -> None:
        candles = _candles(60)
        timestamp = candles[-1].timestamp
        assert timestamp is not None

        vectors = PaperFeatureGenerationService().generate(
            candles=candles,
            prediction_timestamps=(timestamp,),
            ordered_feature_names=MODEL_FEATURE_NAMES,
        )

        self.assertEqual(len(vectors), 1)
        self.assertEqual(vectors[0].feature_names, MODEL_FEATURE_NAMES)
        self.assertEqual(len(vectors[0].feature_values), 12)
        self.assertEqual(len(vectors[0].feature_vector_hash), 64)

    def test_artifact_only_inference_is_repeatable(self) -> None:
        service = PaperInferenceService(_prediction_service())
        candle_timestamp = START + timedelta(days=59)
        vector = PaperFeatureGenerationService().generate(
            candles=_candles(60),
            prediction_timestamps=(candle_timestamp,),
            ordered_feature_names=MODEL_FEATURE_NAMES,
        )[0]

        first = service.predict(vector)
        second = service.predict(vector)

        self.assertEqual(first, second)
        self.assertEqual(first.predicted_float_hex, (0.02).hex())
        self.assertFalse(hasattr(service, "fit"))

    def test_cycle_defers_buy_until_next_observation_open(self) -> None:
        engine = PaperTradingEngine()
        configuration = _configuration()
        inference = PaperInferenceService(_prediction_service())
        initial = engine.run_cycle(
            snapshot=_snapshot(_candles(60)),
            prior_state=PaperTradingState.initial(Decimal("100000")),
            configuration=configuration,
            inference=inference,
        )
        assert initial is not None

        self.assertEqual(len(initial.state.predictions), 1)
        self.assertEqual(initial.state.signals[0].action.value, "BUY")
        self.assertEqual(len(initial.state.fills), 0)
        self.assertIsNone(initial.state.open_position)

        second = engine.run_cycle(
            snapshot=_snapshot(_candles(61)),
            prior_state=initial.state,
            configuration=configuration,
            inference=inference,
        )
        assert second is not None

        self.assertEqual(second.processed_observation_count, 1)
        self.assertEqual(len(second.state.predictions), 2)
        self.assertEqual(len(second.state.fills), 1)
        self.assertEqual(
            second.state.fills[0].execution_timestamp,
            START + timedelta(days=60),
        )
        self.assertIsNotNone(second.state.open_position)
        self.assertEqual(len(second.state.audit_log), 16)

    def test_risk_stop_generates_simulated_forced_exit(self) -> None:
        configuration = replace(
            _configuration(),
            risk=replace(
                _risk(),
                stop_loss=StopLossRule(Decimal("0.01")),
            ),
        )
        engine = PaperTradingEngine()
        inference = PaperInferenceService(_prediction_service())
        first = engine.run_cycle(
            snapshot=_snapshot(_candles(60)),
            prior_state=PaperTradingState.initial(Decimal("100000")),
            configuration=configuration,
            inference=inference,
        )
        assert first is not None
        candles = list(_candles(61))
        latest = candles[-1]
        candles[-1] = replace(
            latest,
            low=Decimal("100"),
        )

        second = engine.run_cycle(
            snapshot=_snapshot(tuple(candles)),
            prior_state=first.state,
            configuration=configuration,
            inference=inference,
        )
        assert second is not None

        self.assertEqual(len(second.state.fills), 2)
        self.assertEqual(len(second.state.closed_trades), 1)
        self.assertIsNone(second.state.open_position)
        self.assertEqual(
            second.state.risk_events[-1].event_type.value,
            "forced_exit",
        )

    def test_report_and_state_round_trip_are_repeatable(self) -> None:
        configuration = _configuration()
        cycle = PaperTradingEngine().run_cycle(
            snapshot=_snapshot(_candles(60)),
            prior_state=PaperTradingState.initial(Decimal("100000")),
            configuration=configuration,
            inference=PaperInferenceService(_prediction_service()),
        )
        assert cycle is not None
        provenance = _provenance()

        first = build_paper_trading_report(
            configuration=configuration,
            provenance=provenance,
            cycle=cycle,
            previous_report_id=None,
            previous_result_hash=None,
        )
        second = build_paper_trading_report(
            configuration=configuration,
            provenance=provenance,
            cycle=cycle,
            previous_report_id=None,
            previous_result_hash=None,
        )

        self.assertEqual(first.configuration_hash, second.configuration_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(state_from_report(first.payload), cycle.state)
        self.assertFalse(first.payload["verification"]["fit_invoked"])
        self.assertFalse(
            first.payload["verification"]["live_broker_orders_placed"]
        )

    def test_repeated_market_timestamp_is_idempotent(self) -> None:
        engine = PaperTradingEngine()
        snapshot = _snapshot(_candles(60))
        first = engine.run_cycle(
            snapshot=snapshot,
            prior_state=PaperTradingState.initial(Decimal("100000")),
            configuration=_configuration(),
            inference=PaperInferenceService(_prediction_service()),
        )
        assert first is not None

        repeated = engine.run_cycle(
            snapshot=snapshot,
            prior_state=first.state,
            configuration=_configuration(),
            inference=PaperInferenceService(_prediction_service()),
        )

        self.assertIsNone(repeated)

    def test_missing_execution_observation_is_rejected(self) -> None:
        engine = PaperTradingEngine()
        first = engine.run_cycle(
            snapshot=_snapshot(_candles(60)),
            prior_state=PaperTradingState.initial(Decimal("100000")),
            configuration=_configuration(),
            inference=PaperInferenceService(_prediction_service()),
        )
        assert first is not None
        candles = (*_candles(60), _candle(61))

        with self.assertRaisesRegex(ValueError, "skip"):
            engine.run_cycle(
                snapshot=_snapshot(candles),
                prior_state=first.state,
                configuration=_configuration(),
                inference=PaperInferenceService(_prediction_service()),
            )

    def test_scheduler_is_configurable_and_stoppable(self) -> None:
        scheduler = PredictionScheduler(interval_seconds=30)
        timestamp = START
        self.assertEqual(
            scheduler.next_run_after(timestamp),
            timestamp + timedelta(seconds=30),
        )

        async def exercise() -> int:
            calls = 0
            stop = asyncio.Event()

            async def cycle() -> None:
                nonlocal calls
                calls += 1
                stop.set()

            await scheduler.run(cycle, stop)
            return calls

        self.assertEqual(asyncio.run(exercise()), 1)

    def test_paper_modules_expose_no_training_call(self) -> None:
        root = Path(inspect.getfile(PaperTradingEngine)).parent
        source = "\n".join(
            path.read_text()
            for path in sorted(root.glob("*.py"))
        )

        self.assertNotIn(".fit(", source)
        self.assertNotIn("sklearn", source)
        self.assertNotIn("model_packaging", source)


class PaperMarketDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_service_excludes_incomplete_candle(self) -> None:
        as_of = START + timedelta(days=61, hours=12)
        provider = _Provider((*_candles(61), _candle(61)))

        snapshot = await KrakenPaperMarketDataService(
            provider
        ).fetch_completed_candles(
            as_of=as_of,
            history_observations=60,
        )

        self.assertEqual(len(snapshot.candles), 60)
        self.assertEqual(
            snapshot.completed_through,
            START + timedelta(days=60),
        )
        self.assertEqual(len(snapshot.market_data_hash), 64)


class _Provider:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles

    async def get_historical_candle_page(self, **_):
        return HistoricalCandlePage(
            candles=self._candles,
            next_since=0,
        )


def _artifact() -> PackagedRidgeInference:
    size = len(MODEL_FEATURE_NAMES)
    means = np.zeros(size, dtype=np.float64)
    scales = np.ones(size, dtype=np.float64)
    coefficients = np.zeros(size, dtype=np.float64)
    for array in (means, scales, coefficients):
        array.setflags(write=False)
    return PackagedRidgeInference(
        feature_names=MODEL_FEATURE_NAMES,
        scaler_means=means,
        scaler_scales=scales,
        coefficients=coefficients,
        intercept=0.02,
        artifact_sha256="a" * 64,
        state_sha256="b" * 64,
    )


def _prediction_service() -> ProductionPredictionService:
    return ProductionPredictionService(
        LoadedProductionArtifact(
            artifact_id=UUID(int=10),
            configuration_hash="c" * 64,
            artifact_sha256="a" * 64,
            state_sha256="b" * 64,
            model_family="ridge_regression",
            feature_pipeline_version="1.1.0",
            target_version="1.0.0",
            model_dataset_hash="d" * 64,
            training_dataset_hash="e" * 64,
            selected_experiment_id=UUID(int=2),
            holdout_evaluation_report_id=UUID(int=3),
            validation_run_id=UUID(int=4),
            split_hash="f" * 64,
            inference=_artifact(),
        )
    )


def _configuration() -> PaperTradingConfiguration:
    return PaperTradingConfiguration(
        session_name="test-paper-session",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        execution_interval_seconds=86400,
        market_history_observations=60,
        backtest=BacktestConfig(
            initial_capital=Decimal("100000"),
            position_size_fraction=Decimal("0.1"),
            long_only=True,
            transaction_cost_bps=Decimal("10"),
            slippage_bps=Decimal("5"),
            maximum_concurrent_positions=1,
            daily_position_updates=True,
            liquidate_at_end=False,
            annualization_periods=365,
            annual_risk_free_rate=Decimal("0"),
        ),
        strategy=StrategyConfig(
            strategy_name="ridge_threshold_long_only",
            strategy_version="1.0.0",
            buy_threshold=Decimal("0.01"),
            exit_threshold=Decimal("-0.01"),
        ),
        risk=_risk(),
    )


def _risk() -> RiskConfiguration:
    return RiskConfiguration(
        position_sizing=PositionSizingConfig(
            mode=AllocationMode.PERCENTAGE,
            allocation_value=Decimal("0.1"),
            allow_fractional_quantity=True,
        ),
        maximum_position_size=MaximumPositionSizeRule(
            maximum_fraction=Decimal("0.1"),
            maximum_fixed=None,
        ),
        maximum_portfolio_exposure=MaximumPortfolioExposureRule(
            maximum_fraction=Decimal("0.1")
        ),
        maximum_asset_exposure=MaximumAssetExposureRule(
            maximum_fraction=Decimal("0.1")
        ),
        maximum_concurrent_positions=MaximumConcurrentPositionsRule(1),
        stop_loss=None,
        take_profit=None,
        trailing_stop=None,
        daily_loss_limit=None,
        maximum_drawdown=None,
        minimum_cash_reserve=MinimumCashReserveRule(
            minimum_cash=Decimal("1000")
        ),
        trading_cooldown=None,
    )


def _snapshot(candles: tuple[Candle, ...]) -> PaperMarketSnapshot:
    latest = candles[-1].timestamp
    assert latest is not None
    return PaperMarketSnapshot(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        retrieved_at=latest + timedelta(days=1, hours=1),
        completed_through=latest,
        candles=candles,
        market_data_hash="c" * 64,
    )


def _candles(count: int) -> tuple[Candle, ...]:
    return tuple(_candle(index) for index in range(count))


def _candle(index: int) -> Candle:
    price = Decimal("100") + Decimal(index)
    return Candle(
        timestamp=START + timedelta(days=index),
        open=price,
        high=price + Decimal("2"),
        low=price - Decimal("2"),
        close=price + Decimal("1"),
        volume=Decimal("10") + Decimal(index) / Decimal("10"),
    )


def _provenance() -> PaperTradingProvenance:
    return PaperTradingProvenance(
        inference_artifact_id=UUID(int=1),
        inference_artifact_sha256="a" * 64,
        inference_state_sha256="b" * 64,
        inference_configuration_hash="c" * 64,
        selected_experiment_id=UUID(int=2),
        holdout_evaluation_report_id=UUID(int=3),
        model_dataset_hash="d" * 64,
        training_dataset_hash="e" * 64,
        feature_pipeline_version="1.1.0",
        target_version="1.0.0",
        validation_run_id=UUID(int=4),
        split_hash="f" * 64,
    )
