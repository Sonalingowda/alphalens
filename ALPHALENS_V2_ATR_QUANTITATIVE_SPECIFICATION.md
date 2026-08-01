# AlphaLens v2 ATR Quantitative Specification

**Document type:** Phase 2 quantitative-definition recommendation

**Candidate:** `ATR-01` Average True Range only

**Specification status:** Proposed recommendation; not approved

**Implementation status:** Not implemented

**Scope:** BTC/USD completed canonical `5m`, derived `10m`, and native `15m`
evidence

**Research boundary:** This document freezes a complete recommendation for
human review. It does not approve the recommendation, authorize registry or
pipeline changes, establish predictive value, or authorize `ATR-02`,
`ATR-03`, or `ATR-04`.

## 1. Executive Summary

This document recommends one exact definition for Phase 2 candidate `ATR-01`:
a current-inclusive, bounded, 14-observation arithmetic mean of registered
`true_range` version `1.0.0` values. The proposed output is
`average_true_range` version `1.0.0`, expressed in BTC/USD quote-price units,
available at the close of the current candle.

For candle `i`, the recommendation is:

```text
average_true_range_i
    = Q((TR_i + TR_(i-1) + ... + TR_(i-13)) / 14)
```

where every `TR` is the exact, already-quantized output of registered
`true_range` `1.0.0`, and `Q` is the existing feature Decimal policy:
50-digit working precision, quantum `0.000000000000000001`, and
`ROUND_HALF_EVEN`.

The recommendation deliberately uses a simple moving average rather than
Wilder or EMA recursion. A bounded mean is transparent, has finite and exact
dependency provenance, is insensitive to an arbitrary archive start before
its 14-value window, and fits the existing bounded-history metadata. Fourteen
observations are recommended because AlphaLens already uses that exact
point-in-time arithmetic range scale in Candidate C label policy. Reusing the
window and averaging convention reduces avoidable semantic proliferation;
it does not transfer the label policy's purpose, approval, or evidence of
predictive usefulness to this feature.

The first valid output requires 14 consecutive eligible True Range values,
which require 15 consecutive completed candles. Insufficient history produces
no value. Missing, gapped, incompatible, non-finite, negative, or unverifiable
dependency evidence fails closed. A zero result is valid because fourteen
genuinely flat True Range observations are a defined market observation, not
a division error.

Implementation remains blocked after this document until the human approval
gates in Section 9 are satisfied. In particular, the existing computation
interface accepts candles rather than registered dependency values. An
approved additive dependency-value and provenance-membership contract is
required so ATR can consume `true_range` without silently recomputing it.

## 2. Mathematical Definition

### 2.1 Time and source notation

For one supported timeframe, let:

- `D` be its exact duration: 5, 10, or 15 minutes;
- `t_i` be the canonical UTC start timestamp of completed candle `i`;
- `H_i`, `L_i`, and `C_i` be its exact Decimal high, low, and close;
- `C_(i-1)` be the preceding consecutive completed candle's close;
- `Q(x)` be canonical feature quantization to 18 decimal places using
  `ROUND_HALF_EVEN` under Decimal working precision 50; and
- `TR_i` be the registered `true_range` `1.0.0` dependency value at `t_i`.

All observations must belong to BTC/USD and the same single timeframe. Candle
timestamps must be consecutive, aligned UTC boundaries:

```text
t_i - t_(i-1) = D
```

No cross-timeframe observations are mixed in one ATR value.

### 2.2 Frozen True Range dependency

The existing frozen True Range definition is:

```text
TR_raw_i = max(
    H_i - L_i,
    abs(H_i - C_(i-1)),
    abs(L_i - C_(i-1))
)

TR_i = Q(TR_raw_i)
```

`TR_i` first exists at the second consecutive candle and is available at the
close of candle `i`, `t_i + D`.

ATR must consume the registered `TR_i` output and its immutable value
membership. It must not independently recompute hidden True Range values from
OHLC data. This preserves one canonical meaning and implementation for True
Range and makes the dependency chain auditable.

### 2.3 Recommended Average True Range

For every `i` with 14 consecutive eligible registered True Range values,
define:

```text
ATR_raw_i = (Σ from k=0 through 13 of TR_(i-k)) / Decimal(14)

ATR_i = Q(ATR_raw_i)
```

Equivalently:

```text
ATR_i = Q(
    (TR_(i-13) + TR_(i-12) + ... + TR_(i-1) + TR_i) / 14
)
```

The window is trailing and current-inclusive. It contains exactly the ordered
True Range timestamps:

```text
t_(i-13), t_(i-12), ..., t_(i-1), t_i
```

The union of underlying source candles is:

```text
t_(i-14), t_(i-13), ..., t_(i-1), t_i
```

Therefore one ATR value has 14 direct True Range dependencies and 15
transitive source-candle dependencies.

### 2.4 Initialization, seed, and first valid output

This is a bounded rolling definition, not a recursive definition.

- The initialization value is the arithmetic mean of the first 14
  consecutive eligible registered True Range values.
- That first complete 14-value window is the only seed-like initialization;
  there is no earlier guessed value, partial mean, backfill, or recursive
  predecessor state.
- The first valid ATR timestamp is the timestamp of the fourteenth eligible
  True Range value.
- Because True Range itself requires two candles, the first valid ATR output
  is at the fifteenth consecutive completed source candle.
- Later values are defined solely by their own exact 14-value windows. An
  earlier ATR value is not an input to a later one.

This initialization is recommended because it is uniquely determined by the
declared finite window and cannot vary with library defaults or the arbitrary
start of a longer archive.

### 2.5 Point-in-time availability

For the ATR value at `t_i`:

```text
available_at(ATR_i)
    = max(available_at(TR_(i-13)), ..., available_at(TR_i))
    = available_at(TR_i)
    = t_i + D
```

There is no additional computation delay or confirmation boundary in the
quantitative meaning. An operational process may compute later, but it must
not record an earlier availability than `t_i + D`.

The current True Range is included because `ATR-01` is intended to describe
the trailing movement scale through the completed observation `i`. A
strictly-prior range baseline would answer a different shock-comparison
question and belongs, if separately approved, to `ATR-03`.

## 3. Complete Quantitative Specification

### 3.1 Decision table

| Field | Recommended value | Why this value is recommended |
| --- | --- | --- |
| Catalog candidate | `ATR-01` only | It is the foundational P0 ATR candidate. Normalization, shock ratios, and slope/change are distinct hypotheses requiring separate approval. |
| Definition identifier | `average_true_range` | The full name is unambiguous and avoids an undocumented abbreviation in canonical identities. |
| Output identifier | `average_true_range` | One definition produces one scalar with the same stable semantic name. Period and formula remain immutable in definition version `1.0.0`. |
| Definition version | `1.0.0` | This is the first proposed v2 intraday definition. Any semantic change requires a new version. |
| Category | `volatility` | ATR measures trailing completed-candle movement scale and matches the registered True Range category. |
| Instrument | BTC/USD only | This is the only instrument approved by the Phase 1 baseline and catalog scope. |
| Timeframes | Independent `5m`, `10m`, and `15m` | These are the approved intraday timeframes. Independent execution avoids cross-timeframe leakage and preserves native/derived provenance. |
| Direct dependency | Definition `true_range` version `1.0.0`, output `true_range` | Reusing the frozen registered primitive prevents formula duplication and retains exact dependency evidence. |
| Transitive candle fields | Current and preceding `HIGH`, `LOW`, `CLOSE` through the True Range dependency | These are precisely the fields used by frozen True Range; ATR adds no raw source field or hidden input. |
| Period | 14 consecutive True Range observations | It is a familiar, interpretable short-horizon range scale and matches the already approved Candidate C arithmetic scale, reducing inconsistent definitions. It is a convention, not a claimed optimum. |
| Smoothing | Simple arithmetic mean | It is bounded, transparent, exactly reproducible, and free from recursive archive-start sensitivity. |
| Window boundary | Trailing and current-inclusive | It describes movement scale through the current completed candle and is available exactly at its close. |
| History type | `bounded` | Every output depends on a finite 14-TR/15-candle window and no predecessor ATR state. |
| Initialization | Mean of the first complete 14-value True Range window | No partial or guessed value is defensible before the entire declared window exists. |
| Seed | Exact ordered first 14 registered True Range values; no recursive seed | This fully determines initialization without library or provider behavior. |
| Output minimum observations | 15 source candles, equivalent to 14 eligible True Range values | The first True Range consumes two candles; each subsequent consecutive candle adds one eligible True Range. |
| Maximum lookback | 15 source candles | This is the exact union of source candles underlying the 14 direct True Range dependencies. |
| Continuity | Required | A gap changes elapsed-time meaning and invalidates the declared consecutive-observation window. |
| Missing/gapped behavior | Fail closed for a purported complete run; omit only for legitimate leading warm-up | Filling, segmenting, shortening, or resetting would create a different unapproved feature. |
| Input values | Finite Decimal True Range values greater than or equal to zero | Frozen True Range is non-negative. Negative or non-finite dependency values prove invalid evidence. |
| Zero behavior | Fourteen zero True Range values produce exact zero ATR | Zero is mathematically defined and truthfully represents a completely flat window; ATR has no denominator requiring rejection. |
| Output domain | Finite Decimal `>= 0` | An arithmetic mean of valid non-negative True Range values cannot be negative. |
| Output units | Quote-currency price units, USD for BTC/USD | True Range is a price distance, and an arithmetic mean preserves that unit. ATR is not a percentage, return, probability, or annualized volatility. |
| Working arithmetic | Python `Decimal`, local precision 50 | This is the frozen v2 feature arithmetic convention and avoids binary floating-point variance. |
| Quantum | `0.000000000000000001` | This is the frozen feature-value quantum and matches persisted `Numeric(38, 18)` scale. |
| Rounding | `ROUND_HALF_EVEN` | This is the frozen canonical feature rounding policy and gives deterministic tie handling. |
| Intermediate rounding | Use the already-quantized registered TR values; sum exactly at precision 50; divide by exact `Decimal(14)`; quantize ATR once at output | This makes dependency identity authoritative and avoids implementation-dependent repeated rounding. |
| Availability rule | `candle_close` | Every dependency is known by the current completed candle close and no later confirmation is needed. |
| Prefix invariance | Mandatory | Appending or changing evidence after `t_i` must not alter `ATR_i`. The bounded trailing formula guarantees this when implemented correctly. |
| Ordering | Registry topological order after `true_range`; output values ordered by candle timestamp and canonical output order | This preserves dependency-before-consumer execution and deterministic pipeline serialization. |
| Complexity | `O(n)` time and `O(14)` bounded working state, excluding retained outputs | The fixed 14-value window has constant bounded cost. A direct 14-value sum is simple and auditable; an equivalent exact rolling sum is optional only if proven byte-identical. |

### 3.2 Proposed registry metadata

The following is a specification record, not a registry modification:

| Metadata field | Proposed value |
| --- | --- |
| `identifier` | `average_true_range` |
| `description` | `Arithmetic mean of the latest 14 consecutive registered True Range values for completed candles.` |
| `category` | `volatility` |
| `definition_version` | `1.0.0` |
| `required_inputs` | Transitive source fields `high`, `low`, `close`, subject to the dependency-contract decision below |
| `supported_timeframes` | `5m`, `10m`, `15m` |
| output identifier | `average_true_range` |
| output description | `Current-inclusive 14-observation arithmetic mean of registered True Range in quote-price units.` |
| output `minimum_observations` | `15` source candles |
| `history_type` | `bounded` |
| `maximum_lookback_observations` | `15` source candles |
| `requires_continuity` | `true` |
| `availability_rule` | `candle_close` |
| `dependencies` | `("true_range",)` with exact compatible definition version `1.0.0` and output `true_range` |
| `implementation_reference` | Proposed future symbol `app.features.atr.AverageTrueRange` |
| `decimal_quantum` | `0.000000000000000001` |

The current metadata can name a dependency definition but cannot pin its
version/output or declare that computation consumes dependency values rather
than raw candles. Before registration, an additive contract must make those
semantics explicit. Until then, the metadata above is not sufficient for an
approved registry entry.

### 3.3 Versioning strategy

If approved, the quantitative definition begins at `average_true_range`
`1.0.0`. The immutable definition digest must cover every field in this
document that affects computation or meaning, including period, smoothing,
window boundary, dependency version/output, warm-up, history type, source
scope, continuity, availability, units, domain, Decimal policy, identifiers,
and edge behavior.

Any change to any of the following requires a new definition version:

- the 14-observation period;
- arithmetic smoothing;
- current-inclusive boundary;
- initialization or seed;
- direct dependency or compatible dependency version;
- minimum observations or maximum lookback;
- supported instrument or timeframes;
- continuity, missing-data, or zero behavior;
- output identifier, units, or domain;
- availability rule; or
- Decimal precision, quantum, intermediate rounding, or final rounding.

Approval and registration would also require a new immutable registry hash
and a new pipeline version. Pipeline `2.0.0`, its existing registry hash,
ordering, values, and historical runs must remain retrievable and unchanged.
This document does not select either new identity.

### 3.4 Research rationale

True Range captures both the completed candle's high-low excursion and gaps
from the preceding close. Its raw one-candle value can be noisy. A trailing
mean provides a stable, auditable estimate of recent movement scale without
using future returns, classifying a volatility regime, or claiming a
probability.

The proposed ATR may support later, separately governed research into
heteroscedasticity, scale normalization, range shocks, and volatility context.
It is expected to be correlated with realized volatility, high-low range
baselines, Bollinger width, and future ATR-derived candidates. Those
relationships require chronological redundancy and ablation analysis; this
specification makes no claim that ATR improves prediction.

## 4. Determinism Requirements

An approved implementation must satisfy all of the following:

1. Consume only immutable registered `true_range` `1.0.0` values from the
   same instrument, timeframe, compatible source snapshot, and pipeline
   evidence chain.
2. Validate exact chronological ordering and one-timeframe adjacency before
   computation.
3. Use the ordered 14-value window ending at the output timestamp; database
   row order or unordered collection iteration must never affect membership.
4. Use only `Decimal` arithmetic with local working precision 50. Binary
   floating point is prohibited.
5. Sum the exact persisted/canonical dependency values, divide by
   `Decimal(14)`, and perform one ATR output quantization with quantum
   `0.000000000000000001` and `ROUND_HALF_EVEN`.
6. Emit only finite, canonically quantized, non-negative Decimal outputs.
7. Omit the first 14 source-candle positions and emit the first output only
   at source-candle position 15.
8. Produce immutable output records. Returned in-memory collections and value
   objects must use the existing frozen/tuple conventions.
9. Order execution after `true_range`, then order values by candle timestamp
   and canonical registry output order.
10. Produce identical values, canonical serialization, registry evidence,
    result hashes, and memberships for repeated execution over identical
    inputs and configuration.
11. Preserve prefix invariance: for every cutoff `t_i`, computation over the
    prefix ending at `t_i` must equal the restriction through `t_i` of a
    computation over any valid longer suffix.
12. Preserve future-suffix isolation: modifying, appending, or removing a
    candle after `t_i` must not change `ATR_i` or any earlier value.
13. Fail closed on missing dependencies, version mismatch, hash mismatch,
    noncanonical precision, duplicate identities, unsupported scope, gaps,
    incomplete candles, invalid availability, or provenance mismatch.

These requirements are recommended because deterministic numeric output
alone is insufficient: AlphaLens must also reproduce exact membership,
ordering, availability, and hash evidence.

## 5. Validation Requirements

### 5.1 Exact formula fixtures

Tests must operate on exact registered dependency values and verify:

| Fixture | Expected result | Purpose |
| --- | --- | --- |
| 13 consecutive eligible TR values | No ATR output | Proves warm-up is never shortened. |
| TR values `1, 2, ..., 14` | `7.500000000000000000` at the 14th TR timestamp | Proves exact window, divisor, first-valid position, and units. |
| Append TR `15` | Next value uses `2, ..., 15` and equals `8.500000000000000000` | Proves rolling membership and current inclusion. |
| Fourteen zero TR values | `0.000000000000000000` | Proves defined zero behavior. |
| One dependency value `0.000000000000000007` and thirteen zeros | `0.000000000000000000` | Exact half-even tie at `0.5` quantum rounds to even zero. |
| One dependency value `0.000000000000000021` and thirteen zeros | `0.000000000000000002` | Exact half-even tie at `1.5` quanta rounds to even two quanta. |

The fixture values are formula-level dependency evidence. Integration tests
must separately construct valid OHLC candles whose registered True Range
outputs are consumed by ATR.

### 5.2 Warm-up, boundary, and scope tests

Required tests must prove:

- zero through fourteen source candles produce no ATR output;
- fifteen source candles produce exactly one ATR output at the fifteenth
  candle timestamp;
- each later consecutive candle produces exactly one additional output;
- the direct dependency window contains exactly 14 ordered True Range value
  memberships and the transitive source union contains exactly 15 candles;
- the current True Range is included and the True Range before the 14-value
  window is excluded;
- `5m`, `10m`, and `15m` computations run independently and use the correct
  adjacency duration;
- any unsupported instrument or timeframe fails closed;
- a missing or duplicate dependency value fails closed;
- a timestamp gap fails the affected run rather than filling, segmenting,
  shortening, or resetting the window;
- incomplete candles and dependencies available after the requested cutoff
  cannot enter computation; and
- zero is accepted while negative, non-Decimal, non-finite, or improperly
  quantized dependency values are rejected.

### 5.3 Availability tests

For an ATR output whose candle starts at UTC `t`, tests must assert exactly:

| Timeframe | `available_at` |
| --- | --- |
| `5m` | `t + 5 minutes` |
| `10m` | `t + 10 minutes` |
| `15m` | `t + 15 minutes` |

Tests must also prove that timezone-naive, non-UTC, misaligned, or future
dependency timestamps are rejected and that no output is available before
the current True Range dependency.

### 5.4 Deterministic and point-in-time tests

Required validation includes:

- exact repeated-run equality;
- byte-identical canonical payloads and hashes for identical evidence;
- prefix-invariance checks at every possible prefix, including all warm-up
  prefixes;
- mutation of every future suffix position without any change to earlier ATR
  values;
- deterministic registry topological order after `true_range`;
- deterministic output ordering within every timestamp;
- rejection of undeclared output names, duplicate identities, registry
  mismatch, dependency-version mismatch, and implementation-metadata
  mismatch;
- exact Decimal quantum and `ROUND_HALF_EVEN` fixtures;
- source snapshot, dependency membership, availability, result-hash, and
  provenance-hash verification; and
- persistence idempotency, immutable exact reuse, transaction rollback, and
  activation only after complete verification if implementation is later
  authorized.

### 5.5 Comparison and research validation

Correct computation does not establish usefulness. Before predictive claims,
the approved research protocol must compare this feature against at least:

- frozen raw `true_range`;
- existing candle range fraction;
- an approved realized-volatility measure, if one is later available; and
- any approved normalized range or Bollinger-width feature that overlaps its
  hypothesis.

Evaluation must use predeclared chronological splits, purge/embargo,
protected final evidence, multiplicity treatment, feature ablation, minimum
sample requirements, and stopping rules. The 14-period choice must not be
tuned after examining protected outcomes under definition version `1.0.0`.

## 6. Provenance Requirements

Every ATR run and value must retain an unbroken, immutable chain containing:

### 6.1 Definition and configuration evidence

- catalog candidate identity `ATR-01`;
- definition identifier and version;
- immutable quantitative-specification digest and approval reference;
- exact period `14`, arithmetic smoothing, bounded history, initialization,
  current-inclusive boundary, continuity, warm-up, lookback, units, domain,
  availability rule, and Decimal policy;
- implementation reference and code/software identity;
- registry schema/version, canonical registry snapshot, registry hash, and
  canonical execution order; and
- new pipeline identity/version and configuration hash assigned only after
  approval.

### 6.2 Direct dependency evidence per ATR value

- exactly 14 ordered engineered-feature value memberships;
- for each member: immutable value identity, definition `true_range`,
  definition version `1.0.0`, output `true_range`, timestamp,
  `available_at`, Decimal value, pipeline/run identity, and integrity hash;
- exact first and last dependency timestamps; and
- an ordered direct-dependency membership hash covered by the ATR value or
  run result hash.

### 6.3 Transitive source evidence

- exact union of the 15 ordered canonical candle identities underlying the
  14 True Range values;
- all source ingestion-batch memberships;
- native/derived timeframe status and exact two-candle 5m derivation
  memberships for every derived 10m candle;
- source snapshot identity, range, data hash, provenance hash, and source
  batch subset hashes;
- provider/source contract, retrieval, validation, completion, conflict, and
  availability evidence; and
- any gaps, exclusions, limitations, or source-quality blockers.

### 6.4 Output and lifecycle evidence

- asset, quote currency, timeframe, candle timestamp, and exact
  `available_at`;
- canonical Decimal output and output identifier;
- point-in-time, prefix-invariance, coverage, and dependency validation
  results;
- canonical result hash covering ordered outputs and memberships;
- computation/run identity and computation time, kept distinct from market
  availability;
- immutable run/value memberships; and
- activation, supersession, suspension, or failure state without deletion or
  historical rewriting.

The existing run-level source and value memberships do not by themselves
express the exact 14 True Range inputs for each ATR value. Before
implementation, architecture approval must confirm how per-value dependency
memberships and their ordered hash are represented without weakening or
duplicating persistence.

## 7. Research Risks

| Risk | Consequence | Required control |
| --- | --- | --- |
| Conventional-period bias | Fourteen observations are conventional, not empirically proven optimal for BTC/USD intraday data. | Freeze 14 before evaluation and do not tune it on protected evidence. |
| Timeframe interpretation | Fourteen observations represent different elapsed horizons on `5m`, `10m`, and `15m`. | Evaluate each timeframe independently and avoid claiming cross-timeframe equivalence. |
| Scale dependence | Quote-price ATR rises mechanically with the general BTC price level. | State units clearly; study normalized ATR only as separately approved `ATR-02`. |
| Outlier sensitivity | One extreme range affects 14 consecutive ATR values. | Retain raw TR evidence and report the limitation; do not winsorize without a new definition. |
| Lag | Arithmetic averaging reacts more slowly than raw True Range. | Treat ATR as trailing scale, not an immediate shock indicator. |
| Multicollinearity | ATR may overlap raw range, realized volatility, range ratios, and Bollinger width. | Use chronological correlation, redundancy, and ablation analysis. |
| Shared-source dependence | `5m` and derived `10m` evidence are not independent. | Retain derivation memberships and account for dependence in research design. |
| Venue/provider scope | BTC/USD candles reflect the approved Kraken evidence contract, not all-market volatility. | Preserve provider provenance and limit claims to the evidence scope. |
| Look-ahead leakage | A current candle's range is unavailable before its close. | Record availability at `t + D` and prohibit incomplete candles. |
| Data snooping | Comparing many ATR periods or smoothers after results can inflate apparent evidence. | Predeclare alternatives and multiplicity treatment in a separate approved protocol. |
| Label-feature coupling | Candidate C uses the same arithmetic ATR14 scale in label construction. | Treat any simultaneous use as a potential mechanical coupling; audit feature/label timing and include ablations. Shared definition consistency is not independent evidence. |
| False volatility interpretation | ATR measures absolute range scale, not return variance, forecast uncertainty, liquidity, confidence, or probability. | Use precise naming and limitation text in all research and downstream consumers. |

## 8. Alternatives Considered

### 8.1 Wilder recursive ATR with period 14

Wilder smoothing is the best-known convention:

```text
ATR_i = ((13 * ATR_(i-1)) + TR_i) / 14
```

It is not recommended for version `1.0.0`. It requires an exact seed and
recursive predecessor chain, retains effectively unbounded historical
influence, is sensitive to archive start and missing-state recovery, and
requires more complex per-value provenance. Those costs are not justified
before research establishes incremental value over a bounded mean.

### 8.2 EMA-smoothed True Range

An EMA could respond faster, but it adds a multiplier convention, seed
choice, recursive state, and strong overlap with the separately governed EMA
family. It is not recommended because the catalog asks for the smallest
defensible foundational ATR definition.

### 8.3 Other arithmetic windows

Windows such as 7, 20, 28, or timeframe-specific periods could be plausible.
None has frozen evidence demonstrating superiority, and choosing different
periods by timeframe would multiply hypotheses and registry meanings. A
single 14-observation window is recommended for definition consistency and
auditability, not because it is asserted optimal.

### 8.4 Strictly prior ATR window

A window ending at `t_(i-1)` avoids including the current range, but it
describes prior scale rather than scale through the current completed candle.
That boundary is useful for a current-range shock ratio and should be
specified under `ATR-03`, not silently embedded in `ATR-01`.

### 8.5 Normalized ATR

Dividing ATR by close or another price reference improves comparability over
time but changes units and introduces a denominator and zero/availability
policy. That is catalog candidate `ATR-02`; including it here would violate
the one-candidate quantitative scope.

### 8.6 Direct recomputation from OHLC

Recomputing True Range inside ATR would fit the current candle-only compute
signature, but it would duplicate frozen logic, hide the registered
dependency, and weaken provenance. It is rejected. Architecture should evolve
additively to supply registered dependency values instead.

### 8.7 Partial-window initialization

Emitting means over 1 through 13 True Range values would change the output's
statistical meaning during warm-up and make early values incomparable. It is
rejected in favor of omission until all 14 values exist.

## 9. Remaining Approval Gates

This recommendation remains unapproved and must not be implemented until all
applicable gates are explicitly satisfied:

1. **Candidate selection:** Human approval must select exactly `ATR-01` and
   the single `average_true_range` output. This document does not select or
   approve `ATR-02`, `ATR-03`, or `ATR-04`.
2. **Quantitative definition:** Human review must explicitly approve or reject
   the complete formula, period, arithmetic smoothing, current-inclusive
   boundary, initialization, seed treatment, warm-up, lookback, continuity,
   zero behavior, timeframes, units, Decimal policy, identifiers, version,
   fixtures, and research hypothesis in this document.
3. **Definition freeze evidence:** After approval, record an immutable exact
   document digest and approval reference. Editing an approved quantitative
   meaning requires a new specification/version rather than silent changes.
4. **Dependency contract:** Approve an additive feature-computation contract
   that supplies registered dependency values and pins compatible dependency
   definition/output versions. Do not stretch the candle-only interface or
   recompute hidden True Range.
5. **Dependency provenance:** Approve how each ATR value retains its exact 14
   ordered True Range value memberships and transitive 15-candle evidence,
   including hash coverage, while reusing existing persistence architecture.
6. **Registry release:** Only after the prior gates pass, create and review a
   new immutable registry declaration/order/hash. The existing registry and
   pipeline `2.0.0` must remain unchanged.
7. **Pipeline release:** Assign and approve a new pipeline version only during
   a separately authorized implementation task. This document does not choose
   or modify a pipeline version.
8. **Operational evidence:** Before research use, verify an authorized real
   Phase 1 source snapshot and readiness evidence for each selected
   timeframe. The implementation baseline alone is not data adequacy.
9. **Validation approval:** Approve exact formula, edge, warm-up,
   availability, gap, precision, prefix, suffix-mutation, provenance,
   persistence, and failure fixtures before activation.
10. **Research protocol:** Before any predictive evaluation, freeze
    chronological splits, purge/embargo, protected evidence, metrics,
    baselines, redundancy/ablation analysis, multiplicity treatment, minimum
    sample requirements, and stopping rules.
11. **Label-coupling review:** Explicitly assess the consequences of using the
    same ATR14 arithmetic scale in Candidate C labels and as an input feature.
    This must not be treated as independent corroborating evidence.
12. **Implementation authorization:** Issue a separate engineering change
    request before changing code, contracts, registry, pipeline, persistence,
    migrations, or tests.

Until these gates pass, `average_true_range` is a complete quantitative
recommendation only. It is not an approved feature and may not enter an
active registry, pipeline, dataset, model, context, decision, ranking, or
explanation.
