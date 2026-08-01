# AlphaLens v2 Deterministic Backtest Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B validation specification

## 1. Scope

This framework defines point-in-time replay of research policies over immutable
historical evidence. A backtest evaluates policy outputs against an approved
research outcome definition. It SHALL NOT simulate brokerage execution,
portfolio management, position sizing, or profitability unless separately
authorized contracts and data exist.

## 2. Definitions

Let (D_v) be a frozen dataset, (\pi_v) a versioned candidate policy, and
(\mathcal E=(e_1,\ldots,e_n)) the canonical event stream ordered by
availability and stable identity. Replay is

\[
B(D_v,\pi_v,c)=\{(e_i,o_i,z_i)\}_{i=1}^n,
\]

where (c) is configuration, (o_i) immutable policy output or explicit
unavailability, and (z_i) the complete trace/provenance. Identical inputs MUST
produce identical ordered outputs and hashes.

## 3. Replay Semantics

The engine SHALL support:

- **event replay:** process each available event exactly once in canonical order;
- **policy replay:** apply one immutable policy version without runtime refit;
- **snapshot replay:** reconstruct point-in-time market, feature, context, and
  policy state at a cutoff;
- **experiment replay:** reproduce partitions, outputs, exclusions, and metrics.

State may use only the prefix (\mathcal I_t). Later data SHALL NOT change an
earlier output. Mutable global caches, wall-clock decisions, insertion order,
and unrecorded randomness are prohibited.

## 4. Inputs and Outputs

Inputs MUST include dataset/version/hash, policy/version/hash, split and
availability contracts, parameters, initial state, code identity, precision,
and deterministic seed where mathematically necessary. Outputs MUST include
every attempt, decision/unavailable state, evidence trace, lifecycle event,
exclusion, metric input, checkpoint, configuration hash, and result hash.

No missing output may be reclassified as `WAIT`. No future outcome may enter
detection, assessment, score, rank, plan, or explanation generation.

## 5. Assumptions and Dependencies

Replay assumes deterministic policy definitions, immutable inputs, stable
serialization, and sufficient historical prefixes. It depends on the Historical
Dataset Framework, approved research policy, outcome/label policy, metric
specification, and walk-forward partitions. It assumes no fillability or market
impact from candle data.

## 6. Validation Methodology

Required tests are exact rerun equality, prefix invariance, future perturbation,
out-of-order input rejection, duplicate idempotence/conflict failure, checkpoint
restart, event/snapshot/policy replay equivalence, missing-input faults, clock
boundary tests, state reset between folds, and hash verification.

Fault injection MUST cover unavailable source, corrupt artifact, policy mismatch,
partial batch, interrupted replay, and invalid state transition. Every fault
must fail closed with immutable audit evidence.

## 7. Acceptance Methodology

Backtest infrastructure is accepted only when deterministic replay and all
methodological invariants pass on canonical fixtures and at least one approved
non-promotional experiment. Policy performance acceptance is separate and uses
preregistered metrics and criteria. A reproducible unfavorable result is a
successful infrastructure run, not a successful policy.

## 8. Future Work

Future implementations MAY add scalable execution, durable checkpoints, and
additional policy adapters only without changing replay semantics. Trade-level
or cost-aware simulation requires future data and execution-research contracts;
it is not implied here.
