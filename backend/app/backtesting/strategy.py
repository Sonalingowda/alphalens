"""Strategy contracts and the predeclared Ridge threshold strategy."""

from typing import Protocol

from app.backtesting.models import (
    PredictionPoint,
    SignalAction,
    StrategyConfig,
    TradingSignal,
)


class Strategy(Protocol):
    """A deterministic mapping from one immutable prediction to a signal."""

    @property
    def configuration(self) -> StrategyConfig: ...

    def generate_signal(
        self,
        prediction: PredictionPoint,
    ) -> TradingSignal: ...


class RidgeThresholdLongOnlyStrategy:
    """Generate BUY/HOLD/EXIT from fixed forward-return thresholds."""

    def __init__(self, configuration: StrategyConfig) -> None:
        self._configuration = configuration

    @property
    def configuration(self) -> StrategyConfig:
        return self._configuration

    def generate_signal(
        self,
        prediction: PredictionPoint,
    ) -> TradingSignal:
        if (
            prediction.predicted_forward_return
            > self.configuration.buy_threshold
        ):
            action = SignalAction.BUY
        elif (
            prediction.predicted_forward_return
            < self.configuration.exit_threshold
        ):
            action = SignalAction.EXIT
        else:
            action = SignalAction.HOLD
        return TradingSignal(
            prediction_timestamp=prediction.prediction_timestamp,
            action=action,
            predicted_forward_return=(
                prediction.predicted_forward_return
            ),
            strategy_name=self.configuration.strategy_name,
            strategy_version=self.configuration.strategy_version,
            source_prediction_hash=prediction.evidence_hash,
        )

