# AlphaLens Continuity Acceptance Recovery

Date: 2026-11-02  
Branch: `fix/warmup-finalized-candle-overlap-20261102`  
Base: `ef62887e64b5f0b17327681692628fca2af71812`

## Result

**PARTIAL.** The warmup/live overlap defect was reproduced, explained, repaired, and verified with genuine Binance data. The requested six-hour observation was not completed; therefore continuous six-hour and reconnect acceptance remain unvalidated.

## Overlap mismatch root cause

The preserved log showed a mismatch for candle open time `2026-11-01T19:15:00Z` after REST warmup and WebSocket processing overlapped. Warmup calculated an inclusive REST `endTime` at the current five-minute boundary. Binance returned the currently open `19:15Z` kline. `_completed_candle_from_rest_kline` assigned a synthetic event time one second after the kline close, so warmup treated that still-open candle as completed and persisted it. The WebSocket later supplied the finalized candle with the same immutable identity but different finalized content/provenance. The repository correctly preserved the immutable winner and did not create a duplicate, but emitted `persisted_snapshot_mismatch`.

The preserved row remained Binance-provenanced and the database contained one row for the identity. This was an ingestion-finality defect, not evidence of fabricated data or a duplicate database row.

## Repair

- Warmup now rejects any REST candle whose `close_time` is not strictly before the observed UTC time.
- Bounded REST gap recovery applies the same finality check.
- Rejection is explicit and logged as `open_warmup_candle_rejected`.
- Existing immutable records are not deleted or rewritten.
- Regression coverage verifies that a current open candle is not persisted.

## Genuine Binance verification

The repaired worker fetched 250 Binance REST rows and explicitly rejected the current open `19:25Z` candle. It then connected to Binance WebSocket and processed the finalized `19:25Z` candle at `19:30Z`.

Observed repaired run:

- Connected: `2026-11-01T19:26:55Z`
- Finalized candle processed: 1
- Incomplete updates: 89
- Reconnects: 0
- Processor `PROCESSED`: 1
- Gap status: `CLEAR`
- Checkpoint last candle: `2026-11-01T19:25:00Z`
- Final worker state: `STOPPED`
- No `persisted_snapshot_mismatch`, `live_candle_gap`, or reconnect warning occurred in the repaired run.

The prior continuity database contained 253 market snapshots with 253 distinct IDs and zero five-minute chronology gaps. All inspected market snapshots carried Binance provenance. A restorable PostgreSQL backup was created before the repaired run:

`/private/tmp/alphalens-continuity-recovery-baseline-20261102.dump`

SHA-256: `2193f8944bbeada5da6088b1a0f07453d876337aa8088a8ec72af9a5853f94b4`

## Tests

- Full backend: **958 passed, 30 skipped**, 497 subtests passed.
- Focused live/continuous/ownership suite: **61 passed**.
- Ruff: passed.
- Python compilation: passed.
- Diff check: passed.

## Localhost/browser

The existing localhost services remained available. HTTP checks previously returned frontend login 200, runtime status 200, and truthful `/health` `ARTIFACT_UNAVAILABLE`. No browser automation session with a legitimate authenticated local session was available in this acceptance, so visual freshness and dashboard timestamp advancement remain unverified.

## Acceptance classification

| Area | Result |
|---|---|
| Mismatch diagnosis | PASS |
| Open-candle prevention | PASS |
| Immutable winner preservation | PASS |
| Genuine Binance smoke ingestion | PASS |
| Checkpoint persistence | PASS |
| Six-hour continuity | PARTIAL / NOT COMPLETED |
| Reconnect resilience | NOT VALIDATED |
| Controlled network interruption | NOT VALIDATED |
| Browser freshness | NOT VALIDATED |
| Overall | PARTIAL |

