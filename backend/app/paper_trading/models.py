"""Typed state and configuration for paper trading."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.backtesting.models import (
    BacktestConfig,
    ClosedTrade,
    ExecutionFill,
    PortfolioSnapshot,
    StrategyConfig,
    TradingSignal,
)
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.models import RiskEvent


PAPER_TRADING_ENGINE_VERSION = "2.0.0"
PAPER_TRADING_REPORT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class PaperTradingConfiguration:
    session_name: str
    asset_identifier: str
    quote_currency: str
    timeframe: str
    execution_interval_seconds: int
    market_history_observations: int
    backtest: BacktestConfig
    strategy: StrategyConfig
    risk: RiskConfiguration

    def __post_init__(self) -> None:
        if not self.session_name.strip():
            raise ValueError("Paper trading session name is required.")
        if (
            self.asset_identifier != "BTC"
            or self.quote_currency != "USD"
            or self.timeframe != "1d"
        ):
            raise ValueError(
                "Paper trading v2.0.0 supports BTC/USD daily only."
            )
        if self.execution_interval_seconds <= 0:
            raise ValueError("Execution interval must be positive.")
        if self.market_history_observations < 50:
            raise ValueError(
                "At least 50 observations are required for features."
            )
        if self.backtest.liquidate_at_end:
            raise ValueError(
                "A continuous paper portfolio cannot liquidate at cycle end."
            )


@dataclass(frozen=True, slots=True)
class PaperMarketSnapshot:
    provider: str
    asset_identifier: str
    quote_currency: str
    timeframe: str
    retrieved_at: datetime
    completed_through: datetime
    candles: tuple[Any, ...]
    market_data_hash: str


@dataclass(frozen=True, slots=True)
class PaperFeatureVector:
    timestamp: datetime
    feature_names: tuple[str, ...]
    feature_values: tuple[Decimal, ...]
    pipeline_version: str
    feature_vector_hash: str


@dataclass(frozen=True, slots=True)
class PaperPrediction:
    prediction_timestamp: datetime
    predicted_forward_return: Decimal
    predicted_float_hex: str
    evidence_hash: str
    feature_vector_hash: str
    inference_artifact_sha256: str


@dataclass(frozen=True, slots=True)
class PaperPosition:
    entry_fill: ExecutionFill
    high_watermark: Decimal


@dataclass(frozen=True, slots=True)
class PaperAuditEvent:
    sequence: int
    observation_timestamp: datetime
    event_type: str
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class PaperTradingState:
    observation_sequence: int
    last_market_timestamp: datetime | None
    cash: Decimal
    open_position: PaperPosition | None
    pending_signal: TradingSignal | None
    portfolio_peak: Decimal
    previous_close_equity: Decimal
    last_exit_observation_index: int | None
    predictions: tuple[PaperPrediction, ...]
    signals: tuple[TradingSignal, ...]
    fills: tuple[ExecutionFill, ...]
    closed_trades: tuple[ClosedTrade, ...]
    risk_events: tuple[RiskEvent, ...]
    portfolio_history: tuple[PortfolioSnapshot, ...]
    audit_log: tuple[PaperAuditEvent, ...]

    @classmethod
    def initial(cls, initial_capital: Decimal) -> "PaperTradingState":
        return cls(
            observation_sequence=0,
            last_market_timestamp=None,
            cash=initial_capital,
            open_position=None,
            pending_signal=None,
            portfolio_peak=initial_capital,
            previous_close_equity=initial_capital,
            last_exit_observation_index=None,
            predictions=(),
            signals=(),
            fills=(),
            closed_trades=(),
            risk_events=(),
            portfolio_history=(),
            audit_log=(),
        )


@dataclass(frozen=True, slots=True)
class PaperTradingProvenance:
    inference_artifact_id: UUID
    inference_artifact_sha256: str
    inference_state_sha256: str
    inference_configuration_hash: str
    selected_experiment_id: UUID
    holdout_evaluation_report_id: UUID
    model_dataset_hash: str
    training_dataset_hash: str
    feature_pipeline_version: str
    target_version: str
    validation_run_id: UUID
    split_hash: str


@dataclass(frozen=True, slots=True)
class PaperCycleResult:
    state: PaperTradingState
    processed_observation_count: int
    cycle_start: datetime
    cycle_end: datetime
    market_data_hash: str
    feature_set_hash: str
    prediction_set_hash: str

