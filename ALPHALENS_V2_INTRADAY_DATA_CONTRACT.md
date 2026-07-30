# AlphaLens v2 Intraday Data Contract

## Status and Scope

This document governs Phase 2 — Intraday Data Foundation. It is subordinate to
the approved Phase 1 baseline.

Phase 2 covers validated, persisted BTC/USD candles for `5m`, `10m`, and
`15m`. It does not authorize feature engineering, targets, decisions,
confidence, ranking, scanner behavior, overlays, or removal of v1 data paths.

## Provider Decision

Kraken Spot REST remains the approved provider for Phase 2.

- The existing provider abstraction and keyless public endpoint are reused.
- Kraken provides native `5m` and `15m` OHLC intervals.
- Kraken does not provide a native `10m` OHLC interval.
- The current uncommitted candle is always returned and must be excluded.
- The endpoint returns at most the latest 720 entries; older OHLC entries
  cannot be retrieved through this endpoint regardless of the `since` value.
- Phase 2 must record that provider limit honestly and must not represent
  repeated overlapping requests as historical pagination.

The practical initial history is therefore the completed portion of Kraken’s
latest 720 native candles. Later ingestion runs accumulate genuinely new
observations through insert-only persistence.

## Canonical Market Scope

| Field | Value |
| --- | --- |
| Instrument | `BTC/USD` |
| Base asset | `BTC` |
| Quote currency | `USD` |
| Native timeframes | `5m`, `15m` |
| Derived timeframe | `10m` |
| Timestamp timezone | UTC |
| Timestamp meaning | Inclusive candle-open time |
| Range convention | Half-open `[start, end)` |
| Numeric representation | Exact decimal |

## Completed-Candle Rule

A candle is complete only when its entire interval ends at or before the
retrieval cutoff.

The retrieval cutoff is the current UTC time floored to the requested
timeframe boundary. Any candle whose open timestamp is equal to or later than
that cutoff is incomplete and must be excluded before validation and
persistence.

Incomplete candles are counted in ingestion audit evidence. They are never
silently accepted, repaired, or persisted as complete.

## UTC Alignment

Canonical timestamps must align exactly to their timeframe:

- `5m`: minute divisible by 5, with zero seconds and microseconds;
- `10m`: minute divisible by 10, with zero seconds and microseconds;
- `15m`: minute divisible by 15, with zero seconds and microseconds.

Misaligned candles fail validation and are not persisted as valid data.

## Deterministic 10-Minute Derivation

Each `10m` candle is derived from exactly two consecutive, complete,
UTC-aligned `5m` candles.

For a `10m` bucket beginning at time `t`:

- source timestamps must be exactly `t` and `t + 5m`;
- `open` is the first source candle’s open;
- `high` is the maximum source high;
- `low` is the minimum source low;
- `close` is the second source candle’s close; and
- `volume` is the exact sum of source volume.

If either source candle is absent, incomplete, malformed, duplicated, or
misaligned, no `10m` candle is created for that bucket. The resulting gap is
reported by validation; it is not interpolated or fabricated.

Derived-candle provenance must identify:

- Kraken as the originating provider;
- `5m` as the source timeframe;
- the deterministic derivation method and version; and
- the source ingestion batch.

## Validation Requirements

Every native and derived series must be checked before persistence for:

- timezone-aware timestamps;
- exact UTC timeframe alignment;
- strict chronological ordering;
- duplicate timestamps;
- gaps inside the provider-available requested range;
- missing required fields;
- non-positive OHLC prices;
- negative volume;
- invalid OHLC relationships; and
- incomplete candles.

Validation reports issues without modifying source observations.

## Persistence and Immutability

- Existing exact numeric candle columns remain authoritative.
- The uniqueness key remains instrument, quote currency, timeframe, and candle
  timestamp.
- Persistence is insert-only for canonical candles.
- A repeated ingestion may insert only genuinely new timestamps.
- Existing validated candle values must never be overwritten.
- Every attempt creates an immutable ingestion batch record, including failed
  validation.
- Candles from a failed batch are not persisted as valid observations.
- Derived `10m` batches must reference their source `5m` ingestion batch.
- Existing daily v1 candles and ingestion evidence remain unchanged.

## Availability and Backfill Limit

For the initial run, the provider exposes at most 720 recent historical
entries. Kraken also returns the current uncommitted candle, so the observed
payload may contain 721 rows while the completed historical count remains
limited to 720.

The system must report:

- provider row count;
- accepted completed count;
- excluded incomplete count;
- provider limit reached;
- available start and end;
- inserted count;
- stored count; and
- validation issues.

The system must not claim history earlier than the provider actually returned.

## Phase 2 Acceptance Boundary

Phase 2 is complete only when:

- native `5m` and `15m` candles are fetched from Kraken;
- `10m` candles are deterministically derived from validated `5m` evidence;
- all three series pass the approved validation rules;
- all three series are persisted idempotently with complete provenance;
- a repeated ingestion creates no duplicate observations;
- live verification reports actual ranges and counts; and
- existing daily research behavior remains unchanged.
