# AlphaLens Batch 6Z — Economic Quality Report

Status: PASS for deterministic local arithmetic and truthful observability; predictive/economic performance remains NOT VALIDATED.

## Observed population

The owner-facing local database contained 13 genuine persisted thesis records derived from BTCUSDT/5m Detection assessments. They represented two registered detection-family clusters, five non-terminal current states and eight terminal states. All assessment relationships were recorded as `NEW_THESIS` because no exact geometry match was present in the retained sample. This report does not merge or rewrite those records.

The isolated Batch 6Z live database had 3 thesis records, 3 assessment relationships and 8 lifecycle events at the `2026-10-26T20:01:28Z` finalization inspection. Their current states were one `ENTRY_AVAILABLE` and two `MONITORING`; the six-hour aggregate remains incomplete.

The parallel thesis tests did not modify this live database or change any economic assumptions. Economic results therefore remain the previously reported deterministic calculations for genuine persisted plans.

## Deterministic scenario

Input assumptions:

- direction: SELL;
- entry reference: `80178.00000000`;
- target: `80063.478214285714285714`;
- invalidation: `80254.347857142857142857`;
- position notional: USD 500;
- instrument semantics: explicitly short-capable derivative;
- entry fee: 10 bps;
- exit fee: 10 bps;
- entry slippage: 5 bps;
- exit slippage: 5 bps.

Output:

| Measure | Value |
|---|---:|
| Gross target movement | 114.521785714285714286 price points |
| Gross target movement | 0.142834425546017254% |
| Gross target profit | `$0.7141721277300862723315622740` |
| Gross stop movement | 0.095222950364011503% |
| Gross potential loss | `$0.4761147518200575148856294744` |
| Modeled round-trip costs | `$1.5` |
| Estimated net target | `-$0.7858278722699137276684377260` |
| Estimated net stop | `-$1.976114751820057514885629474` |
| Break-even movement | `0.3%` |
| Cost-to-gross-reward ratio | `2.100333997586235931398953202` |
| Economic status | `COSTS_EXCEED_GROSS_TARGET` |

The result demonstrates that a technically valid geometry can be economically unattractive after configured costs. It is not a probability, expected value, profitability forecast or account-rate statement.

## Capital and instrument boundaries

- Position notional is separate from account capital.
- INR 500 is supported only when an explicit INR/USD rate is supplied.
- No live FX rate was invented.
- Spot SELL returns unavailable because AlphaLens does not assume or execute a naked short.
- No leverage recommendation or trade execution exists.
- No target-arrival estimate, win probability, confidence or model score is exposed.

## Aggregation available now

The API and thesis layer expose direction, thesis identity, lifecycle state, target/stop geometry, original timestamps and economic status under explicit assumptions. Aggregation by direction, state and economic classification is supported without selecting thresholds or suppressing unfavorable records. A six-hour live aggregate is not yet available because the supervised run is still in progress.

## Limitations

- Fees and slippage are configured assumptions, not verified exchange account rates.
- No spread/funding/latency calibration has been established.
- No execution records exist; outcomes are hypothetical geometry observations only.
- No approved model artifact exists.
- No predictive validation or economic performance conclusion is permitted.

Report content hash (excluding this final hash line): `81b76411bd7143c59a118760b05bcd07a8976858be31396d7611fb37c5b2379c`
