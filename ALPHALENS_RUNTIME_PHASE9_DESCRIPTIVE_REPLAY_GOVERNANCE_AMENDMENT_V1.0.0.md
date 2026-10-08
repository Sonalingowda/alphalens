# AlphaLens Runtime Phase 9 Descriptive Replay Governance Amendment v1.0.0

**Amends:** `ALPHALENS_RUNTIME_PHASE9_PAPER_VALIDATION_POLICY_V1.0.0.md`

**Amendment version:** `1.0.0`

**Status:** Documentation-only superseding amendment; requires explicit human approval

**Scope:** The current fixed-policy, operational/descriptive Phase 9 replay only.

**Canonical hash:** `6cb6129c108418d457fbfec755b8952d73aecacd67b61981adef27acf8b3d94b`

## 1. Purpose and preservation

This amendment reconciles the approved Phase 9 scope with the protected-period
language in the v1.0.0 methodology. It applies only to the fixed-policy,
descriptive replay defined below. It does not redesign runtime behavior, alter
production records, or authorize predictive, statistical, or economic claims.

The original `ALPHALENS_RUNTIME_PHASE9_PAPER_VALIDATION_POLICY_V1.0.0.md` is
preserved unchanged as the historical methodology baseline. This amendment
supersedes its conflicting protected-evaluation applicability only for the
scope explicitly stated here.

## 2. Frozen Phase 9 scope

- Population: ranking-admitted opportunities.
- Evaluation unit: one immutable `OpportunityVersion`.
- Scope: real Binance `BTCUSDT`, `5m`.
- Signal window:
  `2026-09-24T13:15:00.019Z` through `2026-09-24T18:05:00.015Z`.
- Population size: 29 OpportunityVersions.
- Outcome categories, reported descriptively only:
  `TARGET_HIT`, `STOP_HIT`, `EXPIRED_BEFORE_ENTRY`,
  `EXPIRED_AFTER_ENTRY`, and `DATA_INSUFFICIENT`.
- Research interval: `signal_timestamp → valid_until`.
- Candle selection: `timestamp > signal_timestamp` and
  `timestamp <= valid_until`; `valid_until` is inclusive.
- The population window restricts `signal_timestamp` only; it does not
  truncate an observation interval that extends beyond the window.
- Purge: not applicable.
- Embargo: not applicable.

All 29 observations remain included. Runtime interval overlap is retained as
descriptive temporal dependence; no clustering, weighting, exclusion, or
dependence estimator is introduced by this amendment.

## 3. Protected statistical evaluation applicability

The protected statistical evaluation requirement is **NOT APPLICABLE** to
this specific Phase 9 replay because the frozen scope contains:

1. no model fitting;
2. no parameter, threshold, or hyperparameter selection;
3. no development-versus-validation comparison;
4. no statistical estimator or significance test; and
5. no predictive or economic acceptance claim.

Accordingly, no statistical holdout is manufactured for this replay. There is
no protected-result-driven tuning or selection. This determination does not
waive protected evaluation requirements for any later confirmatory,
predictive, statistical, or economic study.

## 4. Reconciliation of the v1.0.0 methodology

For this scope only:

- v1.0.0 §6 references to contiguous development, validation, protected
  evaluation, fold purge, and fold embargo are not applicable because this is
  a fixed-policy descriptive replay with no fitted or selected component.
- v1.0.0 §15's mandatory latest-period protected holdout is not applicable.
- v1.0.0 §18's protected-test rule is not a Phase 9 acceptance prerequisite
  for this descriptive-only scope. Its reproducibility, provenance, leakage,
  and adverse-evidence requirements remain applicable.
- v1.0.0 §19's protected-boundary decision is resolved as not applicable for
  this scope. Its remaining unresolved statistical, economic, and predictive
  decisions remain outside this replay and are not silently approved.
- Any other v1.0.0 language that conditions this descriptive replay on a
  statistical protected period is interpreted consistently with this
  amendment.

The amendment does not convert the runtime outcome categories into research
labels, create a binary success/failure outcome, or convert
`DATA_INSUFFICIENT` into failure.

## 5. Explicit exclusions and limits

This replay must not report or imply:

- predictive accuracy or model correctness;
- statistical significance or statistical sufficiency;
- profitability, P&L, Sharpe, drawdown, or economic performance;
- execution feasibility or live-trading readiness; or
- evidence obtained by tuning, favorable subset selection, or protected-result
  inspection.

All adverse, expiry, null, unavailable, and inconclusive runtime outcomes
remain visible.

## 6. Canonical hash construction

The canonical hash uses the repository convention:

- algorithm: SHA-256;
- serialization: sorted-key, compact UTF-8 JSON;
- helper: `app.opportunity_intelligence.domain.canonical_sha256`;
- excluded field: `canonical_hash`.

The exact hash input is:

```json
{"amendment_id":"alphalens_runtime_phase9_descriptive_replay_governance","amends_policy":"alphalens_runtime_phase9_paper_validation","amends_version":"1.0.0","applicability":{"instrument":"BTCUSDT","opportunity_count":29,"population":"ranking-admitted opportunities","scope":"current fixed-policy descriptive-only replay","signal_window_end":"2026-09-24T18:05:00.015Z","signal_window_start":"2026-09-24T13:15:00.019Z","timeframe":"5m"},"canonical_hash_convention":{"algorithm":"SHA-256","hash_excludes":["canonical_hash"],"helper":"app.opportunity_intelligence.domain.canonical_sha256","serialization":"sorted-key compact UTF-8 JSON"},"claims_excluded":["predictive_accuracy","statistical_significance","economic_or_pnl_performance","live_trading_readiness"],"frozen_decisions":{"candle_query":"timestamp > signal_timestamp AND timestamp <= valid_until","embargo":"not_applicable","evaluation_unit":"immutable OpportunityVersion","outcome_categories":["DATA_INSUFFICIENT","EXPIRED_AFTER_ENTRY","EXPIRED_BEFORE_ENTRY","STOP_HIT","TARGET_HIT"],"outcome_interval":"signal_timestamp_to_valid_until","population_window_applies_to":"signal_timestamp_only","protected_statistical_evaluation":"not_applicable","purge":"not_applicable","valid_until_inclusive":true},"protected_boundary_reconciliation":{"protected_result_tuning":"prohibited","reason":["no_model_fitting","no_parameter_threshold_or_hyperparameter_selection","no_development_validation_comparison","no_statistical_estimator_or_testing","no_predictive_or_economic_acceptance_claim"],"statistical_holdout":"not_required_for_this_scope"},"status":"approved_scope_amendment_pending_explicit_human_approval"}
```

SHA-256 of that exact UTF-8 byte sequence is:

`6cb6129c108418d457fbfec755b8952d73aecacd67b61981adef27acf8b3d94b`
