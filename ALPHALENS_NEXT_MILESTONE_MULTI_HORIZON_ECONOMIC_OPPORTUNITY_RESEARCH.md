# AlphaLens Next Milestone Proposal — Multi-Horizon Economically Meaningful Opportunity Research

Status: proposal only. No new dataset acquisition, model fitting, threshold optimization, protected-test access, or strategy promotion is authorized by this document.

## Objective

Measure whether persisted AlphaLens opportunity geometries have economically meaningful, chronologically observable outcomes over 10m, 30m, 1h, 2h and 4h holding horizons. The result must distinguish operational opportunity persistence from predictive accuracy and profitability.

## Fixed research design for approval

- Horizons: 10 minutes, 30 minutes, 1 hour, 2 hours and 4 hours, defined in UTC candle time.
- Entry: a timestamped, point-in-time entry rule applied only after the qualifying closed candle and with no future information.
- Costs: explicit fee, spread, slippage and, where applicable, funding assumptions recorded per experiment; no invented FX or account-rate values.
- Outcomes: first target touch, first stop touch, neither by horizon expiry, and same-candle target/stop ambiguity. Ambiguous bars must remain ambiguous unless approved intrabar evidence exists.
- Time-to-target: report censored observations when no target arrives by the horizon; do not convert them to wins, losses or averages without a stated censoring method.
- Direction/instrument: preserve existing BUY/SELL and spot-versus-derivative semantics. No naked spot short assumption.

## Chronological protocol

1. Freeze and hash the approved source dataset, code version, configuration, feature definitions, event-time cutoff, and all random seeds before analysis.
2. Build labels only from candles strictly after the point-in-time entry. No random train/test split is permitted.
3. Use chronological development, validation and final evaluation partitions. Any threshold, cost assumption, horizon interpretation or feature choice must be selected without inspecting final evaluation outcomes.
4. Retain the full opportunity population, including invalidated, missed, unresolved, unavailable-model and economically unattractive records. Do not select only visually successful cards.
5. Record target-first, stop-first, same-candle ambiguous, timeout/censored and missing-data outcomes separately for every horizon.
6. Pre-register subgroup analyses (direction, detection family, volatility/liquidity regime and economic-cost class) before viewing final results, with multiplicity and small-sample limits documented.

## Required evidence and outputs

- Dataset lineage, point-in-time availability proof, survivorship review and missingness/gap report.
- Per-opportunity ledger containing entry timestamp/price, target, stop, horizon, first qualifying outcome, outcome timestamp, time-to-outcome, cost assumptions and immutable source hashes.
- Horizon-by-horizon counts, censoring rates, target-first/stop-first/ambiguous rates, gross and net movement, and uncertainty intervals.
- Sensitivity table for approved cost ranges; no single favorable cost scenario may be selected after observing results.
- Reproducible run receipt with commit, environment/lockfile, configuration hash, dataset hash, parameters, random states and output hashes.
- Separate conclusions for operational completeness, outcome-label completeness, statistical evidence and economic viability.

## Approval gates before execution

- Approve exact source dataset and availability cutoff.
- Approve entry, target, stop, cost and censoring definitions.
- Approve chronological split boundaries and independent final-evaluation ownership.
- Approve minimum sample-size/uncertainty reporting policy.
- Approve whether any later model or strategy work may use the resulting development evidence.

Until those approvals are recorded, the next engineering work should be limited to protocol review, schema/ledger design, and tests for chronology, label construction, ambiguity handling and reproducibility receipts.
