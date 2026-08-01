# AlphaLens v2 Repository Architecture Review

**Review version:** `1.0.0`
**Status:** Final architecture review

## 1. Review Mandate

This review evaluates the frozen AlphaLens foundation and the final Opportunity
Intelligence contract suite for responsibility ownership, dependency
correctness, determinism, interface stability, and extensibility. It SHALL NOT
authorize changes to completed Phase 0–2 infrastructure.

## 2. Sources Reviewed

The review covers the Product, Decision, Confidence, Research, Feature
Architecture, Core Intelligence, Target Architecture, Migration, and
Architecture Evolution documents; the market-data, feature registry/pipeline,
validation, provenance, persistence, API, inference, research, backtesting, and
legacy paper-trading repository areas; and the fourteen pre-implementation
contracts and specifications completed in this architecture phase.

## 3. Canonical Dependency Architecture

The implementation SHALL preserve this directed dependency graph:

```text
approved sources -> canonical market data -> registered features
                                      \-> market context
features + context -> detection -> assessment -> evidence package
evidence + assessment -> qualification -> scoring -> ranking
ranking + lifecycle -> dashboard / detail / notification
evidence package -> explanation -> dashboard / detail / notification
runtime governance -> observes and may suspend every stage
human review -> outside the computation graph
```

Downstream presentation SHALL reference upstream records. No upstream layer
MAY import or depend on presentation, notification, user preferences, or human
actions.

## 4. Responsibility Ownership

| Responsibility | Sole owner |
| --- | --- |
| Source acquisition and canonical candles | Existing market-data infrastructure |
| Feature mathematics and values | Existing Feature Registry and Pipeline |
| Descriptive market state | Market Context Engine |
| Assessment eligibility | Opportunity Detection Engine |
| `BUY`/`SELL`/`WAIT` semantics | Canonical Decision/Assessment layer |
| Evidence identity and relationships | Evidence Engine and Evidence Taxonomy |
| Publication eligibility | Qualification Engine |
| Score components and aggregate | Scoring Engine under approved policy |
| Relative ordering | Ranking Engine |
| Identity, revisions, freshness, current state | Lifecycle Service |
| Informational levels and ratios | Opportunity Plan Engine under approved policy |
| Canonical factual text | Explanation Engine |
| Delivery intent and attempts | Notification Engine |
| Read projections | Dashboard and Detail APIs |
| Suspension and recovery | Runtime Governance coordinator |
| Trading decision | User, outside AlphaLens |

Indicator calculations SHALL NOT be duplicated downstream. Evidence,
explanation, qualification, score, and rank SHALL remain separate records.

## 5. Circular Dependency Review

The proposed domain graph contains no required circular dependency. The
following edges SHALL be prohibited to preserve acyclicity:

- feature or context engines depending on candidates, scores, or explanations;
- evidence source records depending on rendered explanations;
- qualification depending on rank;
- scoring depending on final rank;
- opportunity identity depending on notification state;
- canonical records depending on dashboard filters or watchlists;
- confidence depending on score, rank, reason count, or narrative strength.

Lifecycle MAY reference ranking and assessment events, while those source
records reference lifecycle identity rather than resolved mutable state. The
implementation SHALL use immutable identifiers/events to avoid a persistence
cycle.

## 6. Existing Repository Alignment

The existing market-data validation, completed-candle semantics, feature
registry, dependency ordering, Decimal arithmetic, append-only feature records,
hashing, provenance, and fail-closed validation are suitable foundations and
SHALL be reused unchanged.

Legacy inference, backtesting, paper-trading, portfolio, order, and execution
modules SHALL NOT be reused as v2 Opportunity Intelligence semantics. They MAY
remain as historical/research artifacts under existing migration governance.
The existing legacy prediction API SHALL remain versioned and isolated until a
separate compatibility/retirement task is approved.

## 7. Interface Stability

Every new domain interface SHALL accept immutable references and return
immutable result records. Policies SHALL be referenced by identifier, semantic
version, and digest. Optional atomic records SHALL be absent when unavailable.
Schema evolution SHALL add compatible optional fields only; changed meaning,
required fields, identity, ordering, or hashing requires a new incompatible
contract version.

## 8. Determinism Review

The contract suite defines point-in-time cutoffs, exact Decimal arithmetic,
canonical collection ordering, stable identities, explicit policy versions,
immutable event histories, deterministic tie interfaces, canonical
serialization, and hash verification. Implementations MUST additionally test
idempotent replay, prefix invariance, future isolation, concurrency conflicts,
and snapshot reconstruction.

## 9. Architectural Risks

| Risk | Impact | Required control |
| --- | --- | --- |
| Quantitative policy remains unapproved | No production opportunity MAY publish | Keep policy-dependent outputs unavailable and complete studies before activation. |
| Confidence conflated with score | Unsupported certainty | Preserve default absence and Confidence Policy gate. |
| Lifecycle/persistence circularity | Ambiguous current state | Use append-only events and immutable source references. |
| Multi-timeframe leakage | Repainting or future use | Require completed higher-timeframe availability. |
| Market scope expansion without contracts | Incompatible evidence | Require approved source/product scope and provider provenance. |
| Legacy execution concepts leak into v2 | Product-boundary violation | Isolate namespaces and prohibit imports into Opportunity Intelligence. |
| Notification duplication | User harm and audit inconsistency | Persist intent, stable deduplication identity, bounded approved retry policy. |
| Mutable dashboard projections | Historical inconsistency | Bind reads and cursors to immutable ranking snapshots. |
| Template drift | Non-reproducible explanations | Version immutable templates and retain sentence evidence mappings. |
| Configuration sprawl | Reproducibility loss | Register, validate, hash, and persist complete policy configurations. |

## 10. Backwards-Compatible Recommendations

Production code SHOULD be introduced under a distinct Opportunity Intelligence
domain namespace while reusing existing persistence/provenance primitives.
Policy registries SHOULD follow existing feature-registry validation patterns
without merging semantic registries. An append-only outbox SHOULD separate
canonical notification intent from external delivery. Read APIs SHOULD be new
versioned projections rather than changes to legacy prediction semantics.

These recommendations preserve existing interfaces and SHALL NOT authorize a
microservice split. A modular monolith SHOULD remain the default until measured
requirements justify extraction.

## 11. Review Conclusion

The target architecture has clear ownership, a directed dependency graph,
stable immutable boundaries, and extension points for quantitative policies.
No redesign of the completed foundation is required. The principal remaining
risks are research and activation governance, not unresolved structural
architecture.
