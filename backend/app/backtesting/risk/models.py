"""Risk decisions and immutable audit events."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.backtesting.models import BacktestResult


class RiskEventType(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ALLOCATION_REDUCED = "allocation_reduced"
    FORCED_EXIT = "forced_exit"
    PROTECTION = "protection"


@dataclass(frozen=True, slots=True)
class EntryRiskContext:
    timestamp: datetime
    observation_index: int
    cash: Decimal
    portfolio_equity: Decimal
    current_portfolio_exposure: Decimal
    current_asset_exposure: Decimal
    open_position_count: int
    portfolio_peak: Decimal
    previous_close_equity: Decimal
    last_exit_observation_index: int | None


@dataclass(frozen=True, slots=True)
class EntryRiskDecision:
    permitted: bool
    requested_cash_allocation: Decimal
    approved_cash_allocation: Decimal
    triggered_rules: tuple[str, ...]
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForcedExitDecision:
    required: bool
    triggered_rules: tuple[str, ...]
    reference_price: Decimal | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class RiskEvent:
    timestamp: datetime
    event_type: RiskEventType
    action: str
    rule_names: tuple[str, ...]
    reason: str
    requested_cash_allocation: Decimal | None
    approved_cash_allocation: Decimal | None
    reference_price: Decimal | None


@dataclass(frozen=True, slots=True)
class RiskManagedBacktestResult:
    backtest_result: BacktestResult
    risk_events: tuple[RiskEvent, ...]

