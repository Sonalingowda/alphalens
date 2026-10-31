# AlphaLens Batch 6AA — Batch 6Z Root-Cause Analysis

Date: 2026-10-31

## Finding

Batch 6Z did not complete its scheduled six-hour window. The retained run began at approximately `2026-10-26T19:49:33Z`, reached its last committed candle at `2026-10-26T21:05:00Z`, and ended in fail-closed quarantine. The scheduled endpoint was approximately `2026-10-27T01:49:33Z`.

Retained evidence measured:

| Measurement | Result |
|---|---:|
| Finalized Binance messages | 65 |
| Incomplete updates filtered | 9,680 |
| Pipeline runs | 17 |
| Processor `PROCESSED` | 17 |
| Processor `QUARANTINED` | 48 |
| `NEW_THESIS` matches | 15 |
| Reconnects | 73 |
| Final checkpoint sequence | 17 |
| Last committed candle | `2026-10-26T21:05:00Z` |
| Final checkpoint status | `QUARANTINED` |
| Missing interval | `2026-10-26T21:10:00Z` through `2026-10-27T20:55:00Z` |

## Cause

The transport experienced repeated reconnects, but the decisive processing defect was ordering between the live service and the continuous processor. The processor detected the chronology gap and quarantined the incoming future candle before the service-level `_repair_gap_history` path could run. The service's existing warmup repair therefore could not repair a gap that the processor had already rejected. Later finalized messages were observed but did not enter the pipeline, explaining 65 finalized messages versus 17 processed runs and 48 quarantines.

The 73 reconnects are transport observations, not evidence of fabricated data or predictive failure. The retained logs do not establish one unique lower-level Binance cause for every reconnect; the accepted conclusion is that reconnect handling did not provide a bounded, verified replay path before checkpoint advancement.

## Repair applied

The continuous processor now accepts a bounded recovery callback. For gaps of at most three 5-minute intervals, the live service requests the exact range from Binance REST using `startTime`/`endTime`, validates symbol, timeframe, chronology, finality, positive OHLCV constraints and exact coverage, then replays the genuine candles through the same serialized processor before the triggering candle. Checkpoint advancement occurs only after successful processing. Larger or unverifiable gaps remain explicitly quarantined.

Duplicate, out-of-order, interrupted-commit, restart, bounded-recovery and oversized-gap cases are covered by deterministic tests. No candle is fabricated or interpolated, and original entry/stop/target geometry is not changed by the repair.

## Evidence boundary

This repair is demonstrated by offline deterministic tests and a bounded local smoke run. It does not convert Batch 6Z into a six-hour PASS and does not establish predictive accuracy.
