# AlphaLens Batch 6XY — Acceptance Matrix

Date: 2026-10-27
Overall result: PARTIAL. Local engineering outcomes are separated from predictive, protected-test and public-launch decisions.

| Requirement | Result | Evidence | Remaining limitation |
|---|---|---|---|
| Preserve original checkout and Batch 6U | PASS | Original path untouched; PID 17902 remained alive. | Continue treating Batch 6U resources as protected. |
| Genuine BTCUSDT/5m feed retained | PASS | Local worker reported healthy Binance public feed, closed-candle-only processing and a finalized candle after restart. | This is operational evidence, not research evidence. |
| Economic BUY/SELL arithmetic | PASS locally | `economic_analysis.py`; 3 focused tests; API/UI route verified. | Assumptions are configurable estimates, not account/exchange facts. |
| INR/USD capital controls | PASS locally | Explicit notional and currency controls; missing FX fails closed. | No live FX source was used. |
| Spot SELL semantics | PASS | Spot returns unavailable for naked short; derivative semantics are explicit. | No trading venue or order execution is enabled. |
| Stable thesis identity | PASS locally | Persistent thesis IDs and unique original assessment relation. | Policy remains diagnostic and requires future validation. |
| Conservative matching | PASS locally | Exact geometry match only; changed geometry is ambiguous; 11 related assessments exposed as one review cluster. | Market-structure similarity is not inferred where unavailable. |
| Immutable original plan/evidence | PASS | Original opportunity records are not rewritten; thesis layer stores original values and hashes. | Historical evidence remains bounded by existing retention. |
| Lifecycle state persistence | PARTIAL | State machine, append-only events and current `ENTRY_MISSED` state verified; unit tests cover target/stop/ambiguity. | No multi-hour outcome trial or execution fill evidence. |
| Target/stop evaluation | PARTIAL | Target-first, stop-first and same-candle ambiguity tests pass. | Full economic outcome tracking is not predictive validation. |
| Multi-hour monitoring | NOT VERIFIED | Timestamps and observation methods exist. | No qualifying multi-hour trial was completed in this batch. |
| Target extensions | NOT VALIDATED | Original target remains immutable; no extension shown as actionable. | Extension proposal rules require separate research and approval. |
| API thesis projection | PASS locally | One primary card with related count and model-unavailable limitations returned by API. | Production authentication was not verified. |
| Frontend thesis-centered view | PASS for local bounded use | Browser showed dashboard/detail/economic section and truthful unavailable states. | No claim of public or production readiness. |
| Model output behavior | PASS fail-closed | No approved artifact; API reports unavailable and health returns `503 ARTIFACT_UNAVAILABLE`. | Gate 6 research and artifact approval required. |
| Notification behavior | NOT AUTHORIZED | No external provider used or enabled. | Separate delivery authorization and provider testing required. |
| Migration upgrade | PASS | Disposable local database reached `20261027_0043`; pre-migration dump verified with `pg_restore --list`. | Rollback was not independently verified. |
| Migration rollback/re-upgrade | BLOCKED | Local role lacked `CREATEDB` for an independent disposable rollback database. | Repeat with a permitted disposable database only. |
| Backend regression suite | PASS | 944 passed, 27 skipped, 497 subtests; 2 warnings. | Skips and warnings remain documented. |
| Backend app/tests Ruff | PASS | `ruff check app tests` passed. | Repository-wide scripts Ruff has 82 inherited findings. |
| Frontend regression | PASS | 34 Vitest tests; Node 22 typecheck, lint and build passed. | Production Clerk/browser auth remains unverified. |
| Diff safety | PASS | `git diff --check` passed; no original checkout mutation. | Worktree still contains inherited uncommitted changes. |
| Economic viability as profitability | NOT VALIDATED | Arithmetic can classify modeled costs versus geometry. | No probability, expected value, performance or profitability claim is made. |
| Gate 6 | BLOCKED / NOT VALIDATED | No approved predictive artifact or protected evaluation. | Complete approved research and independent evaluation. |
| Gate 7 | BLOCKED | Runtime image/provenance and production acceptance incomplete. | Complete Gate 7 evidence. |
| Public launch | NOT AUTHORIZED | Explicit project boundary. | Owner launch approval after all gates. |

## Key acceptance interpretation

`PASS` in this matrix means the bounded local engineering behavior was implemented and evidenced. It does not mean predictive validity, economic profitability, production authentication, live notification delivery, Gate 6, Gate 7 or public-launch readiness.

## Evidence identifiers

- Baseline source commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Genuine retained historical dataset hash used by prior authorized replay: `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`
- Pre-migration backup hash: `45a743f73d503f4ef5b5240c5d0100e7bed8191e893e411c0b54ebcaa278463a`
- Current local migration head: `20261027_0043`

Report content hash (excluding this final hash line): `46db47c4416b8ceadac226ff97a0594c95e4406b217b6c3fa027ecc9ec31a621`
