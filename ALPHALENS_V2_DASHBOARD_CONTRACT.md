# AlphaLens v2 Dashboard Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Boundary

The Dashboard is a read-only discovery projection over immutable ranking,
opportunity, lifecycle, and health records. It SHALL contain no research,
detection, qualification, scoring, ranking, confidence, or execution logic.

## 2. Opportunity List Item

Each item MUST contain opportunity and revision identity, instrument,
timeframe, `BUY` or `SELL` stance, lifecycle state, evidence cutoff,
availability and freshness state, rank and ranking-snapshot reference, approved
score and component summary when available, authorized confidence when
available, ordered reason-summary codes, optional plan-presence indicator,
limitations, and detail reference. Absence of optional data MUST remain absence.

## 3. List Response

A response MUST contain API/contract version, ranking snapshot identity and
hash, as-of time, scope, items in canonical rank order, applied presentation
filters, page cursor metadata, freshness/coverage status, partial-failure
disclosures, and response generation time. A valid empty list MUST be distinct
from unavailable service state.

## 4. Filtering, Sorting, and Search

Filters MAY constrain approved instrument, timeframe, stance, lifecycle,
freshness, watchlist membership, and evidence-backed categorical fields.
Canonical rank MUST remain unchanged by presentation filtering.

Default sorting MUST preserve canonical ranking. Alternative sorting SHALL be
explicitly labeled as presentation order and MUST use a complete stable key.
Search SHALL match canonical instrument identifiers and approved indexed text
fields; it SHALL NOT reinterpret evidence or use relevance as opportunity rank.

## 5. Pagination

Pagination MUST be cursor-based over an immutable snapshot and complete stable
ordering key. Cursors MUST bind snapshot, filters, sort, position, and version;
they MUST be integrity protected. Page traversal SHALL NOT mix snapshots.
Expired cursors MUST fail explicitly. Offset pagination SHOULD NOT be used for
changing current views.

## 6. Watchlists

Watchlists SHALL be user-owned presentation preferences containing canonical
market-scope identifiers. They SHALL NOT change detection, qualification,
score, rank, notification eligibility, or evidence. Watchlist mutations SHALL
be audited separately from immutable opportunity evidence.

## 7. Caching

Cache identity MUST include snapshot hash, authorization scope, projection
version, filters, sorting, pagination, and watchlist revision where applicable.
Current-view cache lifetime SHALL NOT exceed the earliest source validity
boundary. Stale responses MUST be labeled or rejected according to API policy;
stale-while-revalidate SHALL NOT represent expired opportunities as current.

## 8. API Boundaries and Validation

The dashboard API MUST be versioned, authenticated where user state is used,
bounded, typed, and read-only with respect to canonical intelligence records.
It MAY record access telemetry but SHALL NOT record a trade decision. Invalid
filters, unsupported sorting, malformed cursors, unavailable snapshots, and
integrity failure MUST return explicit typed errors.
