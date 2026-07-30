"""Deterministic signal generation over ordered prediction evidence."""

from app.backtesting.models import PredictionPoint, TradingSignal
from app.backtesting.strategy import Strategy


def generate_signals(
    predictions: tuple[PredictionPoint, ...],
    strategy: Strategy,
) -> tuple[TradingSignal, ...]:
    timestamps = tuple(item.prediction_timestamp for item in predictions)
    if not predictions or timestamps != tuple(sorted(set(timestamps))):
        raise ValueError(
            "Predictions must be non-empty, unique, and chronological."
        )
    if any(len(item.evidence_hash) != 64 for item in predictions):
        raise ValueError("Every prediction requires SHA-256 evidence.")
    return tuple(strategy.generate_signal(item) for item in predictions)

