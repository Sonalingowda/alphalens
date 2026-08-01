# AlphaLens v2 Opportunity Ranking Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose

The Ranking Engine SHALL create immutable snapshots that order current,
qualified opportunities across approved markets and timeframes. It SHALL NOT
alter assessments, infer confidence, or optimize execution.

## 2. Ranking Inputs and Snapshot

Inputs MUST be a frozen candidate set, immutable qualification records, an
approved scoring policy and results, current lifecycle/freshness evidence, and
an approved ranking policy. A `RankingSnapshot` MUST contain contract and
snapshot identities, scope, as-of and generated-at timestamps, candidate-set
membership, exclusions, ordered memberships, score/component references,
rank and set size, freshness boundaries, policy/code references, predecessor,
candidate-set hash, configuration hash, and result hash.

An empty qualified set SHALL produce a valid immutable empty snapshot.

## 3. Pipeline

The engine MUST freeze membership, canonicalize scope order, validate all
artifacts at one ranking cutoff, exclude structurally invalid or non-current
items, apply qualification, resolve approved scores, apply approved ordering
and tie keys, assign contiguous ranks, verify hashes, persist atomically, and
only then publish.

## 4. Ordering Interfaces

The ranking policy MUST declare, in order:

1. primary score direction and canonical value;
2. freshness component and direction, if used;
3. cross-market comparability rule;
4. cross-timeframe comparability rule;
5. complete deterministic tie key.

Cross-market or cross-timeframe ordering SHALL occur only where the scoring
policy establishes semantic comparability. Otherwise the engine MUST publish
separate scoped snapshots. Freshness SHALL NOT silently override opportunity
quality; it MAY affect order only when the approved policy specifies how.

## 5. Stable Ordering and Ties

Database iteration order, insertion order, process scheduling, random values,
locale rules, and hidden numeric precision SHALL NOT determine rank. The final
tie key MUST resolve every equality using canonical immutable fields and SHALL
be versioned. Until this key is quantitatively approved, cross-opportunity
ranking is unavailable.

## 6. Duplicate Suppression

Duplicate suppression MUST use an approved opportunity identity/continuation
policy. Exact duplicate immutable versions SHALL collapse idempotently.
Multiple current revisions of one opportunity SHALL resolve to the unique
current head. Similar indicators, direction, or symbol SHALL NOT establish a
duplicate. Suppressed memberships and reasons MUST remain in the snapshot.

## 7. Freshness and Lifecycle

Only `QUALIFIED`, current opportunities MAY enter scoring; publication SHALL
transition ranked items under the Lifecycle Contract. Expired, invalidated,
superseded, archived, suspended, or unverifiable items MUST be excluded. A
later rank change SHALL NOT rewrite the earlier snapshot or assessment.

## 8. Determinism and Validation

Identical candidate set, policies, cutoff, and artifacts MUST reproduce the
same membership, exclusions, order, ranks, and hashes. Validation MUST prove
complete membership accounting, score reconstruction, stable ordering,
identity uniqueness, scope compatibility, point-in-time correctness, prefix
invariance of historical snapshots, and transactional publication.

## 9. Policy Gate

This contract defines ordering architecture only. Production ranking requires
approved score semantics, comparability, freshness use, duplicate identity,
and complete tie-breaking rules. No implementation MAY infer them.
