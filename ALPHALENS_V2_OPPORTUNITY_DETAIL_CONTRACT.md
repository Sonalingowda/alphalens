# AlphaLens v2 Opportunity Detail Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Boundary

The Opportunity Detail projection SHALL present one immutable opportunity
revision and its evidence without adding interpretation not present in
canonical records. It SHALL be read-only and SHALL NOT compute indicators,
score, confidence, plans, or lifecycle state.

## 2. Canonical Payload

| Section | Required content |
| --- | --- |
| `contract` | API version, payload version, generated-at, canonical payload hash. |
| `opportunity` | Opportunity/revision, candidate, assessment, decision, instrument, timeframe, stance, policy references. |
| `market_snapshot` | Latest completed canonical candle usable at the response cutoff, source/event/availability times, freshness, and integrity reference. |
| `indicators` | Ordered registry identity/version, value, unit, candle timestamp, availability, and feature-record reference. |
| `context` | Market Context snapshot reference and ordered available/unavailable components. |
| `evidence` | Complete ordered Evidence Taxonomy records or resolvable references, including supporting, contradicting, contextual, and limitations. |
| `explanation` | Deterministic explanation artifact and template/taxonomy versions. |
| `qualification` | Gate results, exclusions, policy, and hash. |
| `scoring_ranking` | Approved components/score, rank, candidate-set size, and ranking snapshot; absent when unavailable. |
| `confidence` | Complete authorized Confidence Contract record or complete absence. |
| `plan` | Complete Opportunity Plan or complete absence. |
| `lifecycle` | Current resolved state and ordered immutable event references. |
| `historical_references` | Predecessors, successors, prior ranking snapshots, and approved historical context references. |
| `audit` | Evidence cutoff, availability, configuration/code identities, lineage root, hashes, limitations, and verification status. |

## 3. Live Market Snapshot Semantics

“Live” SHALL mean the latest completed, validated, available market observation
at the response cutoff. It SHALL NOT imply tick data. The payload MUST
distinguish opportunity evidence snapshot from later display-only market data.
Later price MUST NOT be inserted into the historical assessment, score, plan,
or explanation. Its source and availability MUST be independently disclosed.

## 4. Historical References

Historical references SHALL be immutable links, not rewritten embedded
history. Subsequent outcomes MAY appear only under an approved retrospective
context contract and MUST be visually and structurally separated from evidence
available at assessment time. They SHALL NOT become confidence or proof of
quality.

## 5. Consistency and Absence

All sections MUST refer to compatible instrument, timeframe, opportunity
revision, and evidence cutoff. Optional atomic sections SHALL be wholly present
or absent. Unavailable and absent SHALL remain distinct. Contradicting evidence
and limitations SHALL NOT be omitted by summary projections.

## 6. API and Validation

Resolution MUST use canonical opportunity identity plus optional immutable
revision. Requests for a non-current revision MUST return that historical
revision, not redirect silently. Validation MUST verify authorization, object
existence, reference resolution, chronology, source hashes, projection hash,
and maximum response bounds. Integrity failure MUST fail closed.
