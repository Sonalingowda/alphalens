"""Risk-policy coordinator with independently testable rules."""

from dataclasses import replace
from decimal import Decimal

from app.backtesting.models import MarketBar, ZERO
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.models import (
    EntryRiskContext,
    EntryRiskDecision,
    ForcedExitDecision,
)
from app.backtesting.risk.rules import (
    allocation_caps,
    entry_rejections,
    forced_exit_decision,
)
from app.backtesting.risk.sizing import PositionSizer


class RiskManager:
    def __init__(
        self,
        configuration: RiskConfiguration,
        initial_equity: Decimal,
    ) -> None:
        self.configuration = configuration
        self.position_sizer = PositionSizer(
            configuration.position_sizing
        )
        self.portfolio_peak = initial_equity
        self.previous_close_equity = initial_equity
        self.last_exit_observation_index: int | None = None

    def evaluate_entry(
        self,
        context: EntryRiskContext,
    ) -> EntryRiskDecision:
        context = replace(
            context,
            last_exit_observation_index=(
                self.last_exit_observation_index
            ),
        )
        requested = self.position_sizer.requested_cash_allocation(
            context.portfolio_equity
        )
        rejections = entry_rejections(self.configuration, context)
        if rejections:
            return EntryRiskDecision(
                permitted=False,
                requested_cash_allocation=requested,
                approved_cash_allocation=ZERO,
                triggered_rules=rejections,
                rejection_reasons=rejections,
            )
        caps = allocation_caps(self.configuration, context)
        approved = min((requested, *(value for _, value in caps)))
        triggered = tuple(
            name for name, value in caps if value < requested
        )
        if approved <= ZERO:
            reasons = triggered or ("no_permitted_allocation",)
            return EntryRiskDecision(
                permitted=False,
                requested_cash_allocation=requested,
                approved_cash_allocation=ZERO,
                triggered_rules=reasons,
                rejection_reasons=reasons,
            )
        return EntryRiskDecision(
            permitted=True,
            requested_cash_allocation=requested,
            approved_cash_allocation=approved,
            triggered_rules=triggered,
            rejection_reasons=(),
        )

    def evaluate_open_position(
        self,
        *,
        bar: MarketBar,
        entry_price: Decimal,
        quantity: Decimal,
        prior_high_watermark: Decimal,
        cash: Decimal,
    ) -> ForcedExitDecision:
        return forced_exit_decision(
            configuration=self.configuration,
            bar=bar,
            entry_price=entry_price,
            quantity=quantity,
            prior_high_watermark=prior_high_watermark,
            cash=cash,
            portfolio_peak=self.portfolio_peak,
            previous_close_equity=self.previous_close_equity,
        )

    def record_exit(self, observation_index: int) -> None:
        self.last_exit_observation_index = observation_index

    def record_completed_close(self, portfolio_equity: Decimal) -> None:
        self.portfolio_peak = max(
            self.portfolio_peak,
            portfolio_equity,
        )
        self.previous_close_equity = portfolio_equity
