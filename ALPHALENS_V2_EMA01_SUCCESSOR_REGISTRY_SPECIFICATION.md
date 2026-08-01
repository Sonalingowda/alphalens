# AlphaLens v2 EMA-01 Successor Registry Specification

**Document type:** Feature-specific registry specification

**Feature:** EMA-01

**Status:** Successor registry specification for approval

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

**Architecture reconciliation:**
`ALPHALENS_V2_EMA_ARCHITECTURE_RECONCILIATION.md`

**Quantitative authority:**
`ALPHALENS_V2_EMA01_SUCCESSOR_QUANTITATIVE_SPECIFICATION.md`

**Implementation authority:**
`ALPHALENS_V2_EMA01_SUCCESSOR_IMPLEMENTATION_CONTRACT.md`

## Purpose

This document defines only how EMA-01 is represented, validated, ordered,
discovered, versioned, and audited within the AlphaLens Feature Registry.

It does not define EMA mathematics. All quantitative meaning is inherited
from the EMA-01 Successor Quantitative Specification.

It does not define feature-system architecture. Numeric policy, source
policy, dependency architecture, recursive behavior, pipeline execution,
persistence, provenance, hashing, versioning principles, and deterministic
validation are inherited from the Feature Architecture Standard. EMA-specific
implementation obligations are inherited from the Successor Implementation
Contract.

This specification must be read as a registry projection of those governing
documents. It cannot be used to reinterpret or extend them.

## Supersession

Upon explicit approval, this document supersedes the previous EMA-01 Registry
Specification wherever the previous document conflicts with the governing
documents listed above.

In particular, the successor registration does not declare a registered
Close feature dependency, nullable output, binary-floating output, or
registry self-dependency.

Approval of this specification authorizes only the EMA-01 registry contract.
It does not add EMA-01 to a released registry and does not authorize
implementation or activation.

## 1. Feature Identity

EMA-01 has the following immutable registry identity for its first successor
release:

| Identity element | Canonical value | Registry meaning |
| --- | --- | --- |
| Catalog identity | `EMA-01` | Governance and feature-catalog identity. It is retained in approval and audit evidence. |
| Registry identifier | `exponential_moving_average` | Canonical lowercase-snake-case definition identifier used for registry lookup and execution. |
| Definition version | `1.0.0` | First semantic release of the architecture-conformant EMA-01 quantitative definition. |
| Feature family | `ema` | Stable family classification used by governance and discovery metadata. |
| Category | `trend` | Registry category for a price-baseline feature. It does not imply interpretation or a signal. |
| Implementation reference | `app.features.ema.ExponentialMovingAverage` | Exact implementation symbol that must match the registered implementation. |

The canonical executable definition identity is the pair consisting of
registry identifier and definition version. The catalog identity is not a
substitute lookup identifier.

The values in this table are immutable after release. An alias, display label,
legacy name, filename, class name, or period-derived abbreviation must not be
used as a canonical substitute.

The definition is only eligible for an active registry after all governing
documents, implementation metadata, supported scopes, and recursive-origin
release evidence have been approved and frozen.

## 2. Registry Metadata

### 2.1 Canonical definition metadata

The EMA-01 registry definition must contain the following metadata:

| Metadata field | Required registration |
| --- | --- |
| `identifier` | `exponential_moving_average` |
| `description` | A stable non-predictive description identifying the output as the approved EMA-01 smoothed canonical Close price baseline. |
| `category` | `trend` |
| `definition_version` | `1.0.0` |
| `required_inputs` | Canonical Close only |
| `supported_timeframes` | The repository's approved intraday timeframes: 5-minute, 10-minute, and 15-minute |
| `outputs` | The single output registration defined in Section 3 |
| `history_type` | Recursive |
| `maximum_lookback_observations` | None; recursive origin and lineage govern history |
| `requires_continuity` | True |
| `availability_rule` | Candle close |
| `implementation_reference` | `app.features.ema.ExponentialMovingAverage` |
| `dependencies` | Empty |
| `dependency_contracts` | Empty |
| `decimal_quantum` | The canonical repository feature-value quantum inherited from the Feature Architecture Standard |

The registered description must not contain a formula, trading claim,
predictive claim, interpretation, alternate parameter, or implementation
detail.

### 2.2 Scope metadata

EMA-01 is registered only for the asset, quote-currency, and timeframe scopes
supported by the active AlphaLens intraday feature pipeline. For the successor
release, this means BTC/USD at the approved 5-minute, 10-minute, and 15-minute
timeframes.

Scope restrictions must be enforced by the same registry and pipeline
contracts used by existing intraday features. A consumer must not infer
support for another asset, quote currency, timeframe, daily pipeline, or
legacy pipeline from the EMA name.

Adding a scope that changes source lineage, recursive origin, availability,
or reproducibility requires separate approval and release evidence under
Section 11.

### 2.3 Governing-document metadata

The EMA-01 registry release audit bundle must identify immutable references
and content digests for:

- Feature Architecture Standard;
- EMA Architecture Reconciliation;
- EMA-01 Successor Quantitative Specification;
- EMA-01 Successor Implementation Contract;
- this Successor Registry Specification; and
- the approval record for the registry release.

These references are release and audit evidence. They must be included in the
canonical registry payload only when supported by the active registry schema.
They must not be inserted as unversioned ad hoc fields.

## 3. Output Registration

EMA-01 registers exactly one quantitative output:

| Output metadata | Canonical registration |
| --- | --- |
| Output identifier | `exponential_moving_average` |
| Description | The single price-level output defined by the approved EMA-01 Successor Quantitative Specification. |
| Quantitative type | Finite canonical Decimal under the Feature Architecture Standard |
| Units | Same quote-price units as canonical Close |
| Nullability | Non-null whenever an output record exists |
| Immutability | Immutable after release and persistence |
| Minimum observations | `20` |

The output identifier is globally unique in the active registry. It is the
canonical name used in pipeline ordering, output lookup, result hashing, and
derived-feature dependency contracts.

No alias is part of canonical registration. In particular, `EMA-01`,
`ema_value`, and `ema_20` are not canonical output identifiers for this
successor release.

The registry must not declare seed values, smoothing constants, predecessor
state, distance, slope, crossover, status, quality, signal, or debugging
fields as EMA-01 outputs.

Output type, nullability, immutability, and units record inherited semantics;
they do not alter or independently define the quantitative output.

## 4. Required Source Inputs

EMA-01 declares exactly one feature-specific required source field:
canonical Close.

Close must be represented through the registry's typed candle-field metadata.
It must not be represented as:

- a derived-feature dependency;
- a registry entry named Close;
- an optional input;
- an undeclared implementation read;
- an alias or display label; or
- a fallback to direct persistence access.

The registry's Close declaration means that EMA-01 may read canonical Close
from the validated immutable source snapshot. It does not relax whole-candle
source validation performed by the pipeline.

Adding Open, High, Low, Volume, a transformed price, or any other input would
change the registered contract and requires a new approved feature-definition
version.

## 5. Derived Dependency Declarations

EMA-01 declares no upstream derived-feature dependencies. Its canonical
dependency list and dependency-contract list are both empty.

Registry validation must reject any EMA-01 declaration that names:

- Close or another OHLCV field as a feature dependency;
- True Range, ATR, SMA, another EMA, or any unrelated feature;
- a version-floating dependency;
- an optional fallback dependency; or
- an undeclared dependency output.

The immediately preceding EMA-01 value is recursive value lineage. It is not
an upstream registry dependency and must not appear in the definition's
dependency list or dependency-contract list. Registry self-dependency is
prohibited because it would create a cycle.

The recursive classification in Section 8 tells consumers and the pipeline
that predecessor lineage is required by the Successor Implementation
Contract. It does not convert that lineage into a registry edge.

## 6. Availability Metadata

EMA-01 registers the canonical candle-close availability rule.

The registry metadata must identify the active feature-availability contract
version through the registry snapshot. Consumers must resolve availability
using that contract and the registered timeframe; they must not infer it from
computation time, persistence time, request time, or a display convention.

EMA-01 output cannot be consumed before the close of its corresponding source
candle. Its availability rule must match the shared intraday pipeline and
must not contain an EMA-specific exception.

Changing availability semantics is a breaking contract change requiring new
feature, availability-contract, registry, and pipeline release identities as
applicable.

## 7. Warm-Up Metadata

The sole EMA-01 output registers `minimum_observations` as `20`, copied from
the approved quantitative first-valid boundary.

This field is registry metadata used to validate exact output coverage. It
does not redefine initialization or warm-up mathematics.

The registry must reject:

- a different minimum-observation value;
- zero or a negative value;
- nullable warm-up output metadata;
- a placeholder-output policy;
- a second warm-up rule outside the output declaration; or
- implementation metadata that disagrees with the registered boundary.

Consumers discover mathematical availability through the registered output
metadata. Before the boundary, absence of an EMA-01 output is legitimate
warm-up. At and after the boundary, missing output is not warm-up and must be
treated according to shared fail-closed validation.

## 8. Recursive Classification

EMA-01 is registered with recursive history classification.

The registry must record:

- recursive history type;
- no bounded maximum lookback;
- continuous-source requirement;
- the approved implementation reference; and
- the quantitative and implementation document identities that govern seed,
  origin, replay, and predecessor lineage.

Before activation, the registry release audit bundle must freeze the
canonical recursive-origin evidence for every supported asset and timeframe.
The evidence must bind the origin timestamp and immutable source identity to
the EMA-01 release and supported scope.

The actual predecessor values are run-time and persistence provenance. They
are not embedded in registry metadata.

The registry must reject an EMA-01 definition classified as bounded,
stateless, rolling-window-only, or dependent on mutable persisted state.

## 9. Registry Validation Rules

EMA-01 may enter a released registry only if all shared registry validation
and the following feature-specific checks pass.

### 9.1 Identity validation

Validation must confirm that:

- catalog, registry, and definition-version identities match Section 1;
- the registry identifier is unique;
- the output identifier is unique;
- the definition version is valid semantic versioning;
- the category and implementation reference match Section 2; and
- implementation metadata equals registry metadata exactly.

### 9.2 Input and dependency validation

Validation must confirm that:

- Close is the sole declared feature-specific candle input;
- no registered Close definition is required;
- dependency and dependency-contract collections are empty;
- no registry self-dependency exists; and
- the definition remains acyclic in the complete registry graph.

### 9.3 Output and history validation

Validation must confirm that:

- exactly one output is registered;
- its identifier and metadata match Section 3;
- its minimum observations match Section 7;
- the definition is recursive;
- maximum bounded lookback is absent;
- continuity is required;
- availability is candle close; and
- Decimal quantum matches the repository standard.

### 9.4 Scope and governance validation

Validation must confirm that:

- every supported timeframe and scope is approved;
- recursive-origin evidence exists for every supported series;
- all governing documents and approvals are frozen and mutually consistent;
- document references and digests match the release audit bundle;
- the active registry schema can represent every canonical metadata field;
  and
- no unapproved metadata extension is present.

Any validation failure blocks registry construction or release. Registry
validation must not repair, infer, default, or silently discard conflicting
EMA metadata.

## 10. Discovery Rules

The Feature Registry is the canonical discovery mechanism for EMA-01.

Consumers must discover the definition by exact canonical registry identifier
and, when selecting a historical or pinned definition, exact definition
version. Catalog identity may be used to locate governance records but is not
the executable lookup key.

Discovery must expose, through the canonical registry snapshot:

- definition identity and version;
- description and category;
- required Close source field;
- supported timeframes and applicable scope;
- sole output identifier and minimum observations;
- recursive classification;
- continuity and availability metadata;
- absence of derived dependencies;
- Decimal quantum;
- implementation reference; and
- registry schema, availability contract, and registry configuration
  identities.

Consumers must not discover EMA-01 by scanning implementation modules,
database feature names, legacy daily outputs, aliases, class names, or display
labels.

Version resolution must be explicit. The registry must not silently select a
newer, older, deprecated, or semantically different version for a consumer
that requests an exact EMA-01 version.

Derived features that later consume EMA-01 must declare the exact registry
identifier, definition version, and output identifier from this
specification. Approval of this document does not authorize those consumers.

## 11. Registry Versioning

### 11.1 Initial successor registration

EMA-01 successor registration uses definition version `1.0.0`. This version
identifies the first architecture-conformant release defined by the successor
document set. It does not reuse an incompatible earlier EMA definition.

Adding EMA-01 to the active registry changes canonical registry content. The
release must therefore produce:

- a new immutable registry snapshot;
- a new registry configuration hash; and
- a compatible new pipeline release identity before execution or
  persistence.

Historical registry snapshots and hashes must remain unchanged.

### 11.2 Definition-version changes

A new EMA-01 definition version is required when any registered or inherited
result-affecting semantic changes, including source input, output identity,
warm-up, availability, recursive origin, continuity, Decimal semantics,
implementation meaning, or governing quantitative definition.

Registry descriptions or audit references may change without a feature
semantic version only when the repository's approved versioning policy proves
that canonical registry payload, discovery, computation, output, and
reproduction remain unchanged. Otherwise a new immutable release identity is
required.

### 11.3 Registry-schema changes

This specification uses metadata supported by the current architecture. If a
future registry needs new canonical fields, those fields require an approved
registry-schema version. They must not be added under an existing schema
identity.

Deprecation or retirement may prevent new selection of a definition but must
not delete its historical registry snapshot, hashes, runs, or audit evidence.

## 12. Registry Audit Requirements

The EMA-01 registry release must be independently auditable.

The immutable audit record must preserve:

- catalog identity;
- canonical registry identifier;
- definition version;
- complete canonical metadata payload;
- canonical output registration;
- required source inputs;
- empty derived-dependency declarations;
- availability and warm-up metadata;
- recursive classification and origin evidence by supported series;
- supported scope and timeframes;
- implementation reference;
- registry schema version;
- availability-contract version;
- registry configuration hash;
- pipeline release identity associated with activation;
- governing-document identities and content digests;
- approval references and approval timestamp;
- registration timestamp;
- lifecycle history, including activation, deprecation, supersession, or
  retirement; and
- evidence that registry validation passed.

Audit history must be append-only. A later release must not overwrite an
earlier payload, digest, status transition, origin record, or hash.

An auditor must be able to establish from registry evidence that:

- the executable definition is the approved EMA-01 successor definition;
- Close is a canonical source field rather than a registered dependency;
- no derived dependency or self-dependency was introduced;
- exactly one output was registered;
- implementation metadata matched the registry;
- recursive origin evidence existed before activation;
- the registry hash corresponds to the canonical snapshot; and
- historical registry identities remain reproducible.

## Non-Goals

This registry specification does not define or authorize:

- EMA formulas, parameters, initialization, or recurrence;
- implementation logic;
- feature-pipeline algorithms;
- persistence behavior;
- database tables, columns, constraints, or migrations;
- APIs or endpoints;
- a registered Close feature;
- EMA-02, MACD, RSI, ATR changes, or another feature;
- signals, strategies, trading interpretation, or visualization;
- mutable recursive state; or
- registry activation without the required approval and implementation
  evidence.

## Approval Gate

This specification becomes authoritative only after explicit approval and
freeze.

EMA-01 must not be added to a released registry until:

- all governing documents are approved and their digests are frozen;
- exact implementation metadata matches this specification;
- recursive-origin evidence is frozen for every supported series;
- all registry validation in Section 9 passes;
- the new registry snapshot and hash are reviewed;
- a compatible pipeline release identity is assigned; and
- the complete release audit bundle is retained.

Registration and activation of EMA-01 do not authorize any other feature
family.
