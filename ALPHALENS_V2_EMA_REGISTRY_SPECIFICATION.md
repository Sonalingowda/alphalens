# AlphaLens v2 EMA-01 Registry Specification

**Document type:** Feature Registry architecture specification

**Candidate scope:** `EMA-01` only

**Authority:** Approved EMA-01 Quantitative Specification and approved
EMA-01 Implementation Contract

**Registration status:** Specification only; no registry mutation or feature
implementation is authorized by this document

## 1. Purpose

The AlphaLens Feature Registry is the canonical source of truth for discovering
which feature definitions exist, what each definition means, which versions
are recognized, what dependencies each definition requires, what output schema
it declares, and whether a definition is eligible for a requested use.

Registration exists to prevent anonymous feature columns, hidden dependencies,
ambiguous versions, undeclared outputs, and implementation-specific discovery.
It gives every consumer one deterministic, auditable mechanism for resolving a
feature before computation, persistence, research, context construction, or
any other downstream use.

For EMA-01, the registry is responsible for declaring identity, version,
family, category, lifecycle status, dependency contracts, output schema,
compatibility, documentation, and provenance references. It does not perform
EMA calculations, choose parameters, load values, persist results, or alter
the approved quantitative meaning.

The registry is the canonical discovery mechanism. Filesystem inspection,
class-name lookup, database-column discovery, display labels, import side
effects, and hard-coded consumer lists are not valid substitutes. A consumer
must resolve EMA-01 through an immutable registry snapshot whose identity and
hash can be retained with the consuming result.

Registry content and ordering must be deterministic. The same approved
definitions, versions, dependency declarations, metadata, and lifecycle
revision must produce the same canonical registry payload and registry hash.

## 2. Feature Identity

### 2.1 Canonical identity fields

EMA-01 registration must contain the following canonical identity fields:

| Field | Canonical contract |
| --- | --- |
| `feature_id` | Governance identity `EMA-01`. It uniquely identifies the approved catalog candidate and must not be reused by another feature. |
| `feature_name` | Exact stable lowercase-snake-case feature identifier declared by the approved EMA-01 Quantitative Specification. It must be copied verbatim and must not be inferred from a period, display label, legacy implementation, or library convention. |
| `feature_version` | Exact semantic feature-definition version declared by the approved EMA-01 Quantitative Specification. It identifies one immutable quantitative meaning and output contract. |
| `feature_family` | Canonical family `ema`. It groups the feature for governance and discovery but does not imply compatibility with other EMA-family candidates. |
| `feature_category` | Canonical category `trend`. It describes the primary semantic evidence family and does not assert predictive usefulness. |
| `feature_status` | Lifecycle status from Section 10. The first approved registry revision records `approved`; a separately verified release revision may record `active`. |

The approved Quantitative Specification is authoritative for
`feature_name` and `feature_version`. If either value cannot be resolved from
that immutable artifact and verified by its digest, registration fails closed.
This registry specification does not invent a replacement value.

### 2.2 Composite identity

The canonical definition identity is the combination of `feature_id`,
`feature_name`, and `feature_version`. Registry lookup and audit records must
retain all three. A name without a version, a version without the governance
identity, or a display label is not a complete definition identity.

The canonical registry entry additionally binds the definition identity to
its quantitative-specification digest, output schema, parameter-set identity,
dependency contracts, supported scopes, availability contract, and numeric
policy. Two entries with the same composite identity but different bound
content are conflicting definitions and must be rejected.

### 2.3 Immutability

All canonical identity values are immutable once a registry revision is
released. A lifecycle change does not edit the released entry. It creates a
new immutable registry revision or lifecycle event that references the prior
revision and records the new status.

A different feature name, semantic version, family, category, or governance
identity requires a distinct reviewed registry entry. Historical snapshots
continue to expose the exact identity and status that applied when they were
released.

## 3. Dependency Declaration

### 3.1 Close dependency

EMA-01 must declare the canonical registered Close feature as a mandatory
direct dependency. The dependency declaration must contain:

- Close governance feature identity;
- exact Close feature name;
- exact compatible Close semantic version or an approved closed compatibility
  constraint;
- exact Close output name;
- required value type `Decimal`;
- required units and domain compatibility;
- supported symbol and timeframe compatibility;
- availability-contract compatibility;
- continuity requirement;
- dependency role `current_close`;
- canonical dependency ordinal; and
- immutable Close specification and registry references.

The Close identity, version, and output name must match the approved EMA-01
Quantitative Specification and Implementation Contract. The registry may not
substitute a candle field, legacy daily feature, display alias, or another
price proxy.

If a compatible registered Close feature cannot be resolved, EMA-01 cannot be
registered as active and cannot be discovered as executable. Direct candle
access is not a registry dependency and cannot silently satisfy this contract.

### 3.2 Recursive and initialization lineage

The registry must declare that EMA-01 is recursive and that each
post-initialization value depends on the immediately preceding compatible
EMA-01 value. This self-lineage declaration is a value-level recursive-state
contract, not a graph cycle between separately executable definitions.

The recursive declaration must bind predecessor state to the same
`feature_id`, `feature_name`, `feature_version`, parameter-set identity,
symbol, and timeframe. It must also reference the initialization policy from
the approved quantitative specification.

Initialization dependencies must be described as the exact ordered Close
membership required by the approved quantitative specification. The registry
records the initialization-policy identity and required dependency role; it
does not restate or alter the approved initialization mathematics.

### 3.3 Version and compatibility metadata

Every dependency declaration must include:

- dependency identity and semantic version;
- exact required output identity;
- compatibility-policy identity;
- minimum registry schema capable of expressing the dependency;
- availability-contract version;
- data type, units, and domain expectations;
- whether the dependency is mandatory;
- canonical execution-order relationship; and
- specification digest or immutable documentation reference.

Compatibility must be evaluated before registration and again during
discovery against the selected registry snapshot. A name match alone is
insufficient.

### 3.4 Mandatory resolution and closed dependency set

All declared dependencies are mandatory unless the approved quantitative
specification explicitly marks one optional. EMA-01 must not become `active`
while any mandatory dependency is absent, ambiguous, deprecated without an
approved compatibility path, retired, or incompatible.

The declared dependency set is closed. An implementation may not read or use
any feature, candle field, state record, parameter source, or hidden
intermediate that is not represented by the approved EMA-01 definition and
registry metadata. Adding a dependency changes semantic and provenance
obligations and requires a reviewed versioned registry release.

## 4. Output Schema Registration

### 4.1 Registered quantitative output

EMA-01 registers exactly one quantitative output field under this contract:

| Field name | Description | Field type | Nullable | Immutable |
| --- | --- | --- | --- | --- |
| `ema_value` | EMA-01 value whose meaning, units, period, initialization, recursive behavior, and numeric policy are defined exclusively by the approved EMA-01 Quantitative Specification. | Exact finite `Decimal` under the approved numeric policy | No, once an output record exists | Yes |

No additional quantitative output may be inferred from the family name,
catalog discussion, legacy code, or downstream convenience. In particular,
distance, slope, spread, signal, histogram, normalized, categorical, and
thresholded fields are not part of EMA-01 registration unless the immutable
approved EMA-01 Quantitative Specification explicitly includes them and this
registry specification is superseded through approval. Missing warm-up does
not create a nullable `ema_value`; it means no output record exists for that
timestamp.

### 4.2 Canonical value-record envelope

The registry must associate `ema_value` with the canonical feature-value
envelope required by the approved EMA-01 Implementation Contract. The envelope
contains `feature_id`, `feature_name`, `feature_version`, timestamp, symbol,
timeframe, availability, dependency references, provenance, metadata, result
hash, creation time, and immutability state.

Those envelope fields identify, qualify, and audit the registered output. They
are not additional EMA quantitative outputs and must not be presented as
separate predictive features.

### 4.3 Output constraints

The registered output schema must also retain or resolve:

- exact units from the quantitative specification;
- valid domain from the quantitative specification;
- Decimal working-policy identity, output quantum, and rounding-policy
  identity;
- first-valid and warm-up metadata;
- availability rule;
- symbol and timeframe scope;
- required dependency roles and ordinal schema; and
- immutable output-description digest.

The registry rejects nullability, type, unit, domain, precision, availability,
or output-name declarations that conflict with the approved quantitative
specification or implementation contract.

## 5. Metadata Registration

### 5.1 Required metadata fields

Every EMA-01 registry entry must include:

| Metadata field | Registration contract |
| --- | --- |
| `description` | Stable, non-empty description of EMA-01 as approved feature evidence. It must not contain trading claims or redefine mathematics. |
| `author` | Immutable identity of the human or governed authority responsible for the registry declaration. It must not be inferred from source-control username alone. |
| `semantic_version` | Exact EMA-01 feature-definition version; it must equal `feature_version`. |
| `creation_source` | Governed source of the registration request, including approval artifact identity and change-request reference. |
| `documentation_references` | Ordered immutable references to all governing technical, architecture, quantitative, implementation, and registry documents. |
| `implementation_contract_reference` | Exact identity and digest of `ALPHALENS_V2_EMA_IMPLEMENTATION_CONTRACT.md`. |
| `quantitative_specification_reference` | Exact identity and digest of the approved EMA-01 Quantitative Specification. |
| `technical_requirements_reference` | Exact identity and digest of approved TR-01 Technical Requirements where applicable to the approved dependency chain. |
| `architecture_requirements_reference` | Exact identity and digest of approved ATR-01 Architecture Requirements where applicable to shared registry architecture; this reference does not create an ATR dependency. |
| `registry_specification_reference` | Exact identity and digest of this document. |
| `approval_references` | Ordered immutable human approval records authorizing definition and registry lifecycle transitions. |
| `created_at` | Canonical timezone-aware registration timestamp recorded by the registration authority. It is audit metadata and not market availability. |
| `limitations` | Ordered statements required by the approved definition, including absence of predictive or trading claims. |

### 5.2 Metadata determinism

Fields covered by the registry hash must use canonical names, ordering,
timestamp representation, string normalization, and content-addressed
document references. Free-form metadata that can change without a new registry
revision is prohibited from the canonical entry.

An absent mandatory metadata field blocks registration. Unknown or unresolved
document references must not be replaced with local paths lacking an immutable
digest.

## 6. Compatibility Rules

### 6.1 Semantic version compatibility

EMA-01 compatibility is evaluated across the complete definition contract,
not the version string alone. The registry must compare feature identity,
quantitative-specification digest, parameter-set identity, initialization,
output schema, dependency contracts, availability, numeric policy, supported
scope, and provenance requirements.

Exact version resolution is the default for computation and reproducibility.
A consumer may use a semantic-version constraint only when the registry has an
approved compatibility declaration covering every semantic dimension and the
consumer records the exact resolved version.

### 6.2 Backward-compatible changes

A change is backward-compatible only when it cannot change existing EMA
values, availability, dependencies, output interpretation, registry discovery,
or canonical hashes under the affected schema. Examples may include additive
non-semantic documentation references or clarifying metadata explicitly
excluded from the feature-definition hash.

Even a backward-compatible metadata change creates a new immutable registry
revision. It does not edit a released snapshot.

### 6.3 Breaking changes

A change is breaking when it alters or can alter any of the following:

- feature identifier or output name;
- quantitative meaning or parameter set;
- initialization or recursive-state contract;
- first-valid boundary or warm-up;
- dependency identity, version, output, role, or ordering;
- output type, units, domain, nullability, or precision;
- symbol, timeframe, continuity, or availability scope;
- provenance or hash coverage required for reproducibility; or
- consumer-visible discovery semantics.

A breaking change requires a new feature-definition version, new immutable
registry revision and hash, compatibility review, and a separately approved
pipeline release. Historical versions remain discoverable by exact identity.

### 6.4 Deprecation policy

Deprecation is an explicit lifecycle transition, never deletion. A deprecated
EMA version remains discoverable for historical reproduction, exposes its
replacement reference when one exists, and records deprecation authority,
reason, effective timestamp, and supported-consumer window.

Deprecation does not authorize automatic migration, recomputation, aliasing,
or reinterpretation of historical values. Consumers requesting current active
features must not receive a deprecated version unless their compatibility
policy explicitly permits it and records the exact resolution.

### 6.5 Unsupported versions

An unknown, malformed, retired, incompatible, or consumer-unsupported version
must fail closed with a structured registry resolution state. The registry
must not silently choose the nearest, newest, oldest, or lexically first
version.

## 7. Validation Rules

Before an EMA-01 entry is accepted into any released registry revision, the
registry validator must perform all of the following checks.

### 7.1 Duplicate and uniqueness validation

- `feature_id` is unique to EMA-01 governance identity.
- The combination of feature name and semantic version is unique.
- No other definition owns the registered output name.
- No duplicate dependency identity, role, output, or ordinal exists.
- No conflicting entry shares the same composite identity with different
  content or hashes.
- Canonical ordering contains no duplicate definition position.

Exact duplicate content may be recognized as an idempotent registration replay
only when the complete canonical payload and hash match. It does not create a
second definition.

### 7.2 Identifier and metadata validation

- Canonical identifiers use the repository-approved identifier grammar.
- Semantic versions use the approved semantic-version format.
- Family, category, and lifecycle values belong to their controlled
  vocabularies.
- Required descriptions and documentation references are non-empty.
- Document and approval digests verify.
- `feature_version` and metadata `semantic_version` are identical.
- The quantitative and implementation references resolve to the approved
  immutable artifacts.

### 7.3 Dependency validation

- The registered Close definition exists in the same registry snapshot or an
  explicitly compatible immutable predecessor snapshot.
- Close appears before EMA-01 in canonical dependency order.
- Required Close version and output exist and are compatible.
- Type, units, symbol, timeframe, availability, and provenance contracts
  match EMA-01 requirements.
- Recursive self-lineage and initialization membership contracts match the
  approved EMA documents.
- The executable definition dependency graph remains acyclic; value-level
  predecessor lineage is classified separately and cannot introduce a
  definition-execution cycle.
- Every mandatory dependency resolves exactly once.
- No undeclared dependency is present.

### 7.4 Output-schema validation

- `ema_value` is the only registered EMA-01 quantitative output under this
  specification.
- Its field type is exact Decimal and its nullability is false for emitted
  records.
- Units, domain, precision, rounding, availability, and first-valid metadata
  match the quantitative specification.
- Output and envelope fields do not collide with another registered feature
  output.
- Every field is marked immutable in the released definition contract.

### 7.5 Version and lifecycle validation

- The feature version is consistent with its predecessor version and declared
  compatibility class.
- Breaking changes have not been released as compatible patch metadata.
- The requested lifecycle transition is allowed by Section 10.
- Approval evidence exists for `approved`, `active`, `deprecated`, and
  `retired` transitions.
- An `active` entry has all mandatory dependencies active and compatible.

Any validation failure rejects the proposed registry revision. Partial
registration and best-effort dependency resolution are prohibited.

## 8. Discovery Contract

### 8.1 Canonical lookup

Consumers discover EMA-01 through the Feature Registry using canonical
identity. Supported lookup modes are:

- exact composite lookup by `feature_id`, `feature_name`, and
  `feature_version`;
- exact lookup by feature name and version when governance identity is already
  bound by the consumer contract; and
- lifecycle-filtered lookup by governance identity when an approved resolver
  policy requires the current active version.

Lookup by display description, family alone, category alone, output position,
module name, class name, database column, or unordered search result is
non-canonical.

### 8.2 Version resolution

Exact version requests return only the exact compatible entry or a structured
unavailable result. Current-version resolution must use the registry's
approved lifecycle and compatibility policy and must return the exact resolved
version, registry snapshot identity, and registry hash.

If zero or multiple eligible entries remain after applying the declared
resolution policy, discovery fails closed. Consumers must not choose a version
themselves based on ordering or recency.

### 8.3 Discovery result

A successful discovery result must expose or resolve:

- canonical feature identity;
- exact semantic version and lifecycle status;
- output schema;
- supported symbol and timeframe scope;
- dependency contracts and compatibility constraints;
- initialization and recursive-state metadata;
- availability and numeric-policy identities;
- documentation and approval references;
- registry snapshot identity, schema version, and hash; and
- version and lifecycle lineage.

Discovery returns definition evidence, not feature values. It does not perform
computation, persistence, or source lookup.

### 8.4 Dependency graph visibility

Consumers and auditors must be able to inspect EMA-01's complete declared
definition dependency graph from the registry snapshot. The graph must show
the Close dependency, exact version/output constraints, canonical ordering,
and EMA-01's recursive value-lineage classification.

Graph visibility must distinguish executable definition dependencies from
value-level previous-EMA lineage so that recursion is not misrepresented as a
definition cycle.

This section defines logical discovery behavior only. It does not define an
API, route, transport, request, or response schema.

## 9. Provenance Registration

The registry entry must expose the provenance required to understand and
reproduce the EMA-01 definition independently of any one implementation.

### 9.1 Dependency lineage

Registry provenance must include:

- canonical Close feature identity, version, output, role, and compatibility
  declaration;
- canonical dependency order;
- recursive previous-EMA lineage classification;
- initialization-policy identity and Close-membership role;
- dependency graph digest; and
- predecessor registry snapshot references when dependencies originate from a
  compatible earlier release.

This lineage declares expected evidence relationships. Per-value dependency
memberships remain governed by the Implementation Contract and are not stored
as registry definitions.

### 9.2 Specification references

The entry must retain ordered immutable references and digests for:

- approved EMA-01 Quantitative Specification;
- approved EMA-01 Implementation Contract;
- this EMA-01 Registry Specification;
- approved TR-01 Technical Requirements;
- approved ATR-01 Architecture Requirements where they govern shared feature
  architecture, explicitly marked as non-dependency context; and
- any approved compatibility or lifecycle policy required by registration.

References must identify exact document versions or exact content digests.
Mutable titles or paths without digests are insufficient provenance.

### 9.3 Implementation references

Before an entry becomes `active`, registry provenance must bind the approved
implementation reference, implementation digest, code/version identity,
validation-evidence identity, and compatible pipeline release. A `proposed` or
`approved` definition may omit an implementation reference only when its
status clearly states that it is not executable.

Implementation references do not make source code part of this specification
and do not permit registry discovery through implementation names.

### 9.4 Version lineage

Every version after the first must identify its immediate predecessor and
declare whether the change is backward-compatible or breaking. Lineage must
include change authority, rationale, effective registry revision, replacement
or supersession reference, and the exact fields changed.

Registry provenance must preserve the complete chain across active,
deprecated, and retired versions. A later version never overwrites the
provenance of an earlier one.

## 10. Registry Lifecycle

### 10.1 Lifecycle states

| State | Meaning |
| --- | --- |
| `proposed` | A complete candidate registry entry exists for review but has no approval or execution authority. |
| `approved` | Human authority has approved the definition and registry declaration, but no verified active release is implied. |
| `active` | The approved entry, implementation reference, dependencies, pipeline release, and validation evidence are complete and eligible for declared consumers. |
| `deprecated` | The entry remains historically valid and discoverable but should not be selected for new current use except under an explicit compatibility policy. |
| `retired` | The entry is ineligible for new computation or current discovery but remains available for historical reproduction and audit. |

### 10.2 Allowed transitions

The allowed forward transitions are:

- `proposed` to `approved` after definition and registry approval;
- `approved` to `active` after implementation, dependency, pipeline, and
  validation gates pass;
- `active` to `deprecated` after approved deprecation review; and
- `deprecated` to `retired` after approved retirement review.

No reverse transition is allowed on an existing lifecycle record. If a
deprecated or retired meaning is required again, governance must issue a new
reviewed version or a new immutable lifecycle decision under an explicitly
approved policy; historical state is not rewritten.

Skipping `approved` before activation is prohibited. Direct transition from
`active` to `retired` is prohibited unless a separately approved emergency
integrity policy creates both required immutable events while preserving the
deprecated audit state. Absence of approval, implementation, dependency, or
validation evidence blocks the requested transition.

### 10.3 Lifecycle revision behavior

Every transition creates a new immutable lifecycle event and registry
revision. The prior entry remains retrievable with its original status,
timestamp, registry hash, and approvals. The current registry projection may
identify the latest status, but that projection must be reproducible from the
immutable event history.

Lifecycle status affects eligibility, not historical mathematical truth. A
deprecated or retired version's historical values and definition remain
bound to the version that produced them.

## 11. Audit Requirements

### 11.1 Immutable registry history

The registry must preserve every proposed release, accepted release,
lifecycle transition, compatibility declaration, and validation outcome as
immutable audit evidence. Released entries and snapshots cannot be edited or
deleted.

Each registry snapshot must retain:

- registry identity and schema version;
- canonical ordered definition memberships;
- complete EMA-01 canonical payload;
- registry configuration hash;
- creation and release timestamps;
- predecessor registry snapshot;
- registration authority;
- approval references;
- validation status and report identity; and
- reason-coded rejection evidence for failed proposed revisions where policy
  requires retention.

### 11.2 Version history

Audit history must make every EMA-01 semantic version discoverable by exact
identity. It must show predecessor/successor relationships, compatibility
classification, changed fields, change rationale, lifecycle events,
replacement references, and the registry snapshots in which each version
appeared.

Historical consumers must be able to resolve the exact registry snapshot and
EMA version used by a persisted feature run without consulting the current
registry projection.

### 11.3 Registration timestamp

Every proposed entry, released registry revision, and lifecycle transition
must have a canonical timezone-aware registration timestamp. Registration
time is operational governance evidence and must remain distinct from feature
event time, feature availability, computation time, and source retrieval time.

Timestamps must not determine canonical ordering when explicit registry order
or identity is required. Equal or reordered operational timestamps must not
change semantic registry content.

### 11.4 Approval evidence

Every transition into `approved`, `active`, `deprecated`, or `retired` must
retain:

- approval-record identity;
- approving authority;
- approval timestamp;
- exact approved registry payload or payload hash;
- referenced quantitative, implementation, registry, compatibility, and
  lifecycle documents;
- scope and limitations of approval; and
- predecessor decision where applicable.

An approval statement that cannot be bound to the exact registry content is
insufficient. Missing or mismatched approval evidence fails closed.

### 11.5 Audit reproducibility

An authorized reviewer must be able to reconstruct the canonical EMA-01
registry entry, dependency graph, output schema, metadata, lifecycle state,
version lineage, registry ordering, and registry hash from retained immutable
evidence. Reconstruction must not depend on mutable application state,
database default ordering, network availability, or an implementation module.

## 12. Non-Goals

This specification does not define, authorize, or generate:

- implementation code or implementation-language structure;
- EMA calculations, formulas, parameters, initialization mathematics, or
  numeric derivations;
- persistence logic, value insertion, transaction behavior, or storage
  orchestration;
- API endpoints, routes, transports, request contracts, or response contracts;
- database schema, tables, columns, indexes, constraints, or migrations;
- trading logic, decisions, ranking, confidence, risk management, or order
  execution;
- signal generation, including directional, entry, exit, stop, or objective
  semantics;
- visualization, charting, dashboards, scanners, or user-interface behavior;
- optimization, parameter search, tuning, feature selection, or predictive
  evaluation;
- parallelization, caching products, queues, services, or deployment topology;
- MACD, RSI, ATR changes, or any feature other than EMA-01 registry
  declaration; or
- modification of any approved technical, architecture, quantitative, or
  implementation document.

The registry specification ends at deterministic, immutable,
implementation-independent declaration and discovery of EMA-01. All
implementation and downstream behavior requires its own approved authority.
