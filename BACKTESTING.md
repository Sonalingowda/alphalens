# AlphaLens Backtesting Engine

## Status and Scope

Backtesting Engine v1.0.0 is a deterministic engineering subsystem that
consumes immutable research evidence. It does not train, tune, select, or
modify models, features, targets, validation records, holdout evidence, or
other research artifacts.

The initial implementation is long-only, single-instrument, and daily. It
supports no live trading, broker connection, paper trading, API, or frontend.

## Module Responsibilities

- `strategy.py` maps each immutable model prediction to BUY, HOLD, or EXIT
  using predeclared thresholds.
- `signals.py` validates ordered prediction evidence and produces signals.
- `execution.py` applies configured transaction costs and adverse slippage.
- `positions.py` owns open-position state and closed-trade accounting.
- `portfolio.py` maintains cash, positions, equity, portfolio value, and daily
  returns in chronological order.
- `metrics.py` computes descriptive performance metrics.
- `reporting.py` produces deterministic content-addressed report payloads.
- `persistence/backtests.py` verifies source provenance and stores immutable
  reports separately from the research registry.

## Chronology and Execution

A prediction at daily timestamp `t` is available only after that completed
candle closes. A strategy order generated from that prediction may execute
only at the next observed daily candle's open. Execution therefore cannot use
the close that generated the prediction.

When configured, an open position remaining at the end of the evaluation
period is liquidated at the final completed close. This is identified as
terminal portfolio liquidation, not as a model-generated EXIT signal.

## Explicit Configuration

Every run must provide and persist:

- initial capital;
- position-size fraction;
- long-only mode;
- transaction cost in basis points;
- adverse slippage in basis points;
- maximum concurrent positions;
- daily update policy;
- terminal-liquidation policy;
- annualization periods and annual risk-free rate;
- BUY and EXIT prediction thresholds; and
- strategy name and version.

No strategy threshold, capital assumption, cost, or slippage value is inferred
from observed performance.

## Accounting Conventions

BUY slippage increases the next-open execution price; SELL slippage decreases
it. Transaction costs are charged on executed notional. Position sizing
reserves both notional and entry cost within the configured cash allocation.
Portfolio value is cash plus open quantity marked to the completed daily close.

Undefined metrics are stored as `null`, never fabricated. For example, profit
factor is undefined when there are no losing trades, and trade averages are
undefined when the applicable trade set is empty.

Maximum drawdown is reported as a non-negative peak-to-trough loss fraction.
Daily-return volatility uses sample standard deviation and the configured
annualization factor. CAGR uses the exact elapsed calendar-day range.

## Reproducibility and Audit Evidence

Each persisted report retains its complete configuration, metrics, signals,
execution fills, trade log, equity curve, daily portfolio history, research
provenance, and SHA-256 hashes. Re-running an identical configuration against
identical evidence must reproduce the same configuration, result, input,
signal, trade-log, equity-curve, and daily-history hashes.
