# AlphaLens v2 Ground Truth Label Policy Research Specification

**Specification version:** `1.0.0`

**Artifact class:** Canonical retrospective-label policy contract

**Policy activation:** Disabled

STATUS: REQUIRES RESEARCH

## 1. Scope and Authority

This specification defines the only canonical interface by which future market
outcomes may become AlphaLens research labels. It preserves the frozen
`BUY`/`SELL`/`WAIT` ontology and adds no production decision semantics.

“Ground truth” means the deterministic retrospective outcome assigned by one
explicitly approved label policy. It SHALL NOT mean objective market truth,
causal truth, profitability, fillability, or a production recommendation.

This version defines the complete evaluation algorithm and required parameter
artifact. It deliberately supplies no horizon, barrier, threshold, reference
price, or numeric parameter. Label generation SHALL remain disabled until every
field in Section 5 is populated, justified, versioned, hashed, and explicitly
approved.

## 2. Canonical Units

### 2.1 Observation unit

An observation is one immutable, completed, validated market candle for exactly
one canonical instrument, venue/source scope, and timeframe. Its identity binds
the candle-open timestamp, timeframe, source artifact, completion boundary,
availability, and hash.

### 2.2 Evaluation unit

The evaluation unit is

\[
U=(s,m,\tau,t,c_F,v_F,v_L),
\]

where $s$ is symbol, $m$ market/source scope, $\tau$ timeframe, $t$ prediction-
origin candle timestamp, $c_F$ evidence cutoff, $v_F$ feature snapshot version,
and $v_L$ label-policy version. One evaluation unit produces exactly one
terminal evaluation state.

### 2.3 Opportunity unit

An opportunity unit is the retrospective outcome episode

\[
O_U=(U,r,I_U,E_U),
\]

where $r$ is the policy-defined reference observation/value, $I_U$ the strictly
future outcome interval, and $E_U$ its ordered immutable outcome evidence. It is
research evidence only and SHALL NOT imply an entry, order, or executable path.

## 3. Outcome Vocabulary

The complete terminal evaluation vocabulary is:

| State | Meaning | Dataset eligibility |
| --- | --- | --- |
| `BUY` | A valid complete evaluation determines that the approved upward-outcome predicate became decisive before any approved downward predicate or expiry. | Eligible label |
| `SELL` | A valid complete evaluation determines that the approved downward-outcome predicate became decisive before any approved upward predicate or expiry. It never means exit. | Eligible label |
| `WAIT` | A valid complete evaluation reaches approved expiry with neither directional predicate decisive and no invalidity or ambiguity. | Eligible label |
| `INVALID` | Evaluation cannot produce a valid class because required origin, feature, policy, source, chronology, continuity, domain, or outcome evidence is invalid or unavailable. | Excluded |
| `AMBIGUOUS` | All required evidence exists and is valid, but its resolution cannot determine the required event ordering or unique class under the approved observation granularity/rules. | Excluded |

`INVALID` and `AMBIGUOUS` are audit outcomes, not fourth or fifth model classes.
They SHALL NOT be converted to `WAIT`, imputed, or discarded without a record.

## 4. Information and Look-Ahead Semantics

Let $\mathcal I_U$ contain only evidence available at $c_F$. Features attached
to $U$ MUST be functions of $\mathcal I_U$. Let

\[
I_U=(b_U,e_U]
\]

be the future outcome interval selected by the approved parameter artifact,
with its exact boundary inclusion declared. $b_U$ MUST be no earlier than the
approved prediction-origin boundary, and outcome evidence SHALL NOT enter
$\mathcal I_U$.

Look-ahead is authorized only for retrospective label generation. Every
consumed future observation, event time, availability time, and membership in
$I_U$ MUST be retained as label provenance.

## 5. Mandatory Approved Parameter Artifact

A policy instance is non-executable unless one immutable artifact defines all
of the following without nulls or implicit defaults:

1. policy identifier, semantic version, approval reference, effective scope,
   and configuration digest;
2. instrument, venue/source, timeframe, price convention, and currency/unit;
3. prediction-origin candle and evidence-cutoff rule;
4. first eligible future observation and strict future-separation rule;
5. reference observation, field, timestamp, availability, and transformation;
6. outcome-horizon magnitude, unit, clock basis, and start/end inclusivity;
7. upward predicate, all parameters, units, equality, and event timestamp;
8. downward predicate, all parameters, units, equality, and event timestamp;
9. expiry/`WAIT` predicate;
10. fixed versus point-in-time-derived parameter semantics and warm-up;
11. deterministic event ordering within the available observation granularity;
12. gap-at-boundary and gap-through-event handling;
13. simultaneous and same-observation dual-event handling;
14. missing/incomplete future evidence and end-of-history handling;
15. invalid-domain, zero-denominator, non-finite, and price-invariant handling;
16. feature requirements and exact registry/version dependencies;
17. overlapping-origin generation and dependence-recording rule;
18. label availability and finalization rules for every terminal state;
19. Decimal precision, quantization, rounding, and comparison order;
20. timezone, calendar, expected timestamp grid, and exchange normalization;
21. source conflict, duplicate, correction, and canonical-winner rules;
22. failure/reason-code mapping and precedence;
23. partition-boundary, purge, and embargo dependency semantics;
24. policy serialization, hashing, supersession, and rollback rules; and
25. empirical rationale, assumptions, limitations, and required sensitivity
   study.

The repository's Candidate C recommendation is not this approved artifact; its
approval status remains pending. This specification SHALL NOT copy its numeric
recommendations into an executable policy.

## 6. Deterministic Evaluation Procedure

For each candidate evaluation unit, the label generator MUST execute this order:

1. resolve and verify policy identity, approval, scope, version, and digest;
2. validate canonical origin observation, completion, timestamp, and source;
3. resolve the exact feature snapshot and validate availability at $c_F$;
4. evaluate feature warm-up and policy-required input domains;
5. derive the reference solely by the approved reference rule;
6. construct the complete ordered expected outcome grid $I_U$;
7. resolve each outcome observation by immutable identity, not nearest timestamp;
8. reject invalid, duplicate-conflicted, missing, or incomplete evidence under
   the declared rule;
9. evaluate approved gap/open precedence and directional predicates in the
   declared event order;
10. stop at the first uniquely decisive directional event and assign `BUY` or
    `SELL`;
11. assign `AMBIGUOUS` if valid evidence produces an unresolved simultaneous or
    intrabar ordering under the approved granularity;
12. assign `WAIT` only after the complete valid interval reaches expiry with no
    decisive event;
13. assign `INVALID` for every non-ambiguous failure state;
14. derive label availability, provenance, canonical content, and hashes; and
15. persist one immutable terminal result atomically.

Predicate and event iteration order MUST be encoded in the policy artifact.
Database order, provider response order, process scheduling, randomness, or
unrounded hidden values SHALL NOT affect the outcome.

## 7. Intrabar Ambiguity, Gaps, and Event Ordering

OHLC candles do not reveal the path between open, high, low, and close. If both
directional predicates occur within one candle and the approved observable
ordering cannot distinguish which was first, the result MUST be `AMBIGUOUS`.
Candle direction, proximity, favorable/conservative guessing, or randomness is
prohibited.

Gap handling MUST distinguish a deterministic event observable at the first
field specified by policy from an unobservable within-gap path. The artifact
MUST state field precedence and equality. No behavior is implied here.

## 8. Missingness, Duplicates, and Boundaries

Missing origin candles, mandatory features, reference observations, or outcome
observations MUST follow explicit failure codes and can never yield `WAIT`.
An origin near the current end of history remains pending until its scheduled
outcome boundary can be judged; in a frozen finite dataset it becomes `INVALID`
under the approved end-of-history code if the required interval is unavailable.

Duplicate observations with byte-identical canonical content MAY collapse
idempotently. Conflicting duplicates require a canonical source-conflict
resolution artifact or `INVALID`. Nearest-time substitution is prohibited.

Dataset start/end boundaries MUST include sufficient feature warm-up and future
outcome coverage. Warm-up and tail exclusions remain explicit. Historical data
SHALL NOT be shortened, extended, or selected after class outcomes are viewed.

## 9. Overlap and Dependence

The policy artifact MUST state whether every eligible origin or an ex ante
event-sampling rule generates evaluation units. Valid overlapping outcomes MAY
be retained, but each interval, concurrency, uniqueness/dependence metadata,
and partition crossing MUST be recorded. Overlapping labels SHALL NOT be
treated as independent observations. Downsampling or weighting after outcome
inspection is prohibited.

## 10. Availability and Lifecycle

Label availability is the earliest time at which all evidence required for the
terminal result is complete and validated under policy. It MUST be later than
the feature evidence cutoff for any future-outcome label.

Lifecycle states are `PENDING`, `EVALUATING`, then one of `BUY`, `SELL`, `WAIT`,
`INVALID`, or `AMBIGUOUS`. Terminal records are immutable. A corrected source or
new policy creates a successor label record and explicit supersession; it SHALL
NOT rewrite the earlier result.

## 11. Identity and Provenance

Label identity MUST bind evaluation-unit identity, policy/version/digest,
source scope, feature snapshot, origin timestamp, reference identity, outcome
interval, and label-run identity. Canonical label content MUST include terminal
state, reason code, event/expiry time, available-at, source memberships,
precision metadata, code/configuration identities, predecessor/successor, and
result digest.

`BUY`, `SELL`, and `WAIT` records MUST preserve the complete future evidence
needed to reconstruct them. `INVALID` and `AMBIGUOUS` records MUST preserve all
available evidence and the exact failed/unresolved condition.

## 12. Canonical Failure Taxonomy

At minimum, policy implementations MUST map failures to stable codes in these
families:

- `POLICY_UNAPPROVED`, `POLICY_MISMATCH`, `SCOPE_UNSUPPORTED`;
- `ORIGIN_MISSING`, `ORIGIN_INVALID`, `TIMESTAMP_NONCANONICAL`;
- `FEATURE_WARMUP_INCOMPLETE`, `FEATURE_MISSING`,
  `FEATURE_AVAILABLE_AFTER_CUTOFF`, `FEATURE_VERSION_MISMATCH`;
- `REFERENCE_MISSING`, `REFERENCE_INVALID`, `REFERENCE_DOMAIN_INVALID`;
- `OUTCOME_HORIZON_INCOMPLETE`, `OUTCOME_OBSERVATION_MISSING`,
  `OUTCOME_OBSERVATION_INVALID`, `END_OF_HISTORY`;
- `SOURCE_GAP`, `SOURCE_CONFLICT`, `DUPLICATE_CONFLICT`,
  `SOURCE_HASH_MISMATCH`, `LINEAGE_INCOMPLETE`;
- `PARAMETER_DOMAIN_INVALID`, `NUMERIC_INVARIANT_FAILED`;
- `AMBIGUOUS_SIMULTANEOUS_EVENT`, `AMBIGUOUS_INTRABAR_ORDER`;
- `PARTITION_BOUNDARY_CROSSING`; and
- `INTERNAL_DETERMINISM_FAILURE`, `PERSISTENCE_FAILURE`.

The approved policy MUST define precedence when multiple failures apply. Codes
MAY be specialized but SHALL NOT weaken these distinctions.

## 13. Timezone and Exchange Rules

All canonical timestamps MUST be timezone-aware UTC and lie on the declared
timeframe grid. Original provider timestamp and source timezone metadata remain
in provenance. Exchange/source normalization MUST use an approved mapping for
instrument identity, timestamp semantics, price/volume units, candle completion,
and conflicts. Data from different exchanges SHALL NOT be merged without an
approved market-definition policy.

## 14. Validation and Acceptance

Before activation, a policy instance MUST pass hand-calculated boundary cases,
gap/equality/dual-event cases, missing and duplicate faults, warm-up/tail cases,
timezone boundaries, Decimal invariants, event ordering, exact replay, prefix
invariance, future perturbation, provenance/hash reconstruction, and atomic
failure tests.

Acceptance requires explicit human approval of every Section 5 field before
labels or class summaries are generated. Empirical adequacy criteria and
sensitivity analyses MUST be preregistered separately. No policy instance is
accepted by this document.

## 15. Unresolved Research and Activation Status

The label family, policy parameters, exact scope, horizon, predicates,
reference, event ordering, gap behavior, precision, overlap, partition
dependencies, and adequacy criteria lack an approved parameter artifact.

STATUS: REQUIRES RESEARCH
