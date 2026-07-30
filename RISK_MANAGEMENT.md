# AlphaLens Risk Management Framework

## Status and Boundary

Risk Management Framework v1.0.0 is a modular extension of the deterministic
backtesting engine. It controls simulated order admission, capital allocation,
and protective exits. It does not change model predictions, strategy
thresholds, feature engineering, targets, validation, experiments, or any
immutable research artifact.

## Independent Controls

Each control has its own immutable configuration object and can be enabled or
disabled independently:

- maximum position size by portfolio fraction and optional fixed amount;
- maximum total portfolio exposure;
- maximum exposure to the current asset;
- maximum concurrent positions;
- fixed stop-loss;
- fixed take-profit;
- trailing stop;
- daily loss limit;
- maximum portfolio drawdown;
- fixed minimum cash reserve; and
- trading-observation cooldown after an exit.

Position sizing supports percentage allocation, fixed allocation, and either
fractional or whole-unit quantity.

## Order Admission and Allocation

Every BUY order is checked against every active admission rule before
execution. Concurrent-position, cooldown, daily-loss, and drawdown violations
reject the order. Position-size, exposure, available-cash, and reserve limits
reduce the permitted allocation to their most restrictive bound. An allocation
at or below zero rejects the order.

Risk-reducing SELL orders are never blocked. The report records that all active
rules were considered and that the exit was accepted as risk reducing.

Every acceptance, rejection, and allocation reduction records its timestamp,
rules, reason, requested allocation, approved allocation, and reference price.

## Protective Exit Chronology

Open positions are evaluated once per complete daily OHLC observation.
Stop-loss and take-profit barriers use fixed entry-relative prices. Daily-loss
and drawdown barriers use the prior completed portfolio close and prior
completed portfolio equity peak.

Trailing stops use only the high watermark from observations completed before
the current bar. The current bar's high is incorporated only after the bar
finishes without an exit. This prevents an unknown intrabar high/low ordering
from introducing look-ahead.

If a daily bar touches both a protective downside barrier and a take-profit
barrier, the protective exit takes precedence. If multiple protective barriers
are touched, all are recorded and the most conservative trigger price is used.
Downside fills are gap aware: a bar opening below the trigger uses the lower
opening price. Configured adverse sell slippage and transaction costs are then
applied by the existing execution simulator.

## Reports and Reproducibility

Risk Management Reports are stored separately from backtest and research
records. Each report contains:

- complete backtest, strategy, and risk configuration;
- active and triggered rules;
- accepted and rejected orders;
- allocation reductions and forced exits;
- all portfolio protection events;
- trade log, fills, equity curve, and daily portfolio history;
- source backtest, holdout, prediction, dataset, and experiment provenance;
  and
- SHA-256 hashes for configuration, results, risk events, accepted orders,
  rejected orders, forced exits, and protection events.

An identical configuration and identical evidence must reproduce every hash
exactly and reuse the existing immutable report.
