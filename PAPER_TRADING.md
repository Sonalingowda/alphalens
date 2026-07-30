# AlphaLens Paper Trading Engine

## Status and Boundary

Paper Trading Engine v2.0.0 is a deterministic engineering subsystem for
simulated trading with live public market data. It places no broker orders,
holds no credentials, and moves no real money.

The engine consumes only the immutable production Ridge inference artifact
through the same `ProductionPredictionService` used by the Live Prediction
API. Paper-trading modules do not import training or packaging code and expose
no training method. They never call `fit()`, retrain a model, tune parameters,
modify experiments, or modify any immutable research artifact.

## Modular Services

- `market_data.py` obtains completed BTC/USD daily candles from Kraken and
  rejects incomplete or invalid histories.
- `scheduler.py` provides a configurable cooperative execution interval.
- `features.py` runs the existing point-in-time feature pipeline and requires
  the exact ordered feature schema stored in the inference artifact.
- `inference.py` delegates to the shared production prediction service and
  produces the same content-addressed prediction evidence as the REST API.
- `strategy.py` from the backtesting engine maps predictions to BUY, HOLD, or
  EXIT using the configured thresholds.
- `risk.py` adapts the existing risk framework to persisted paper state.
- `orders.py` uses the existing cost-and-slippage execution simulator.
- `portfolio.py` owns incremental cash, position, P&L, equity, and risk state.
- `performance.py` computes the existing descriptive portfolio metrics.
- `audit.py` hashes every stage of every processed observation.
- `reporting.py` builds deterministic, content-addressed report payloads.
- `persistence/paper_trading.py` verifies the inference artifact and appends
  immutable report records.

## Chronology

Only complete daily UTC candles are accepted. Features for timestamp `t` use
the validated candle prefix ending at `t`. The prediction and signal become
available only after that candle closes.

A BUY or EXIT signal generated at `t` is held as a pending simulated order and
may execute only at the next observed candle's open. If execution cycles were
missed, every unseen completed candle is processed chronologically. The engine
refuses to jump over a missing execution candle.

Open positions are evaluated against the configured risk rules on each newly
completed candle. Protective exits retain the existing conservative intrabar
policy and are simulated only; no live order path exists.

## Configuration

Every paper session requires explicit, persisted values for:

- session name, asset, quote currency, timeframe, history length, and scheduler
  interval;
- initial capital, allocation fraction, costs, slippage, concurrency, update
  policy, annualization, and risk-free rate;
- strategy identity and BUY/EXIT thresholds; and
- all enabled position-sizing, exposure, cash-reserve, stop, take-profit,
  trailing-stop, loss, drawdown, and cooldown rules.

Paper Trading Engine v2.0.0 is deliberately BTC/USD, daily, and long-only.
Configuration values are supplied through typed configuration objects; no
capital, execution-cost, strategy, or risk threshold is inferred from results.

## Portfolio and Audit State

Each cycle tracks cash, equity, open and closed positions, unrealized and
realized P&L through marked portfolio state, daily returns, fills, trades,
signals, risk events, and the full equity history.

Every processed observation records eight ordered audit events: market data,
features, artifact loading, prediction, signal, risk evaluation, simulated
order execution, and portfolio update. Each event is content addressed.

## Immutable Reports

The database stores one append-only report per newly completed market cycle.
Each report links to its predecessor and contains the complete session state,
configuration, predictions, signals, simulated orders, trades, risk events,
portfolio history, performance summary, audit log, and inference provenance.

SHA-256 values cover market input, cycle features, cycle predictions, all
predictions, signals, orders, trades, risk events, portfolio history, audit
events, the verified inference artifact, report configuration, and complete
report result. Reprocessing the same completed candle returns the existing
verified report. Regeneration from identical state must reproduce all hashes.

The report explicitly records that artifact-only inference was used, no fit was
invoked, no live order was placed, and research evidence was not modified.
