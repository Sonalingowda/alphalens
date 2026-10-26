# AlphaLens Public Launch Acceptance Matrix

Status date: 2026-10-26. This matrix records evidence status; it does not grant launch approval.

| Requirement | Status | Evidence | Remaining requirement |
|---|---|---|---|
| Genuine BTCUSDT/5m closed-candle processing | PARTIAL | Batch 6S offline PASS; Batch 6T public 5m WebSocket received one finalized candle in a 370.04-second trial. | Complete and document the authorized full 24-hour live observation. |
| Batch 6U 24-hour observation | IN PROGRESS | Supervised isolated runner PID `17902`; checkpoint sequence 2 at `2026-10-26T17:45:00Z`, READY/no-gap; PostgreSQL/Redis isolated and migrated. | Await final report, full duration, restart/reconnect and continuity evidence. |
| Durable checkpoint and restart recovery | PASS offline / NOT VERIFIED live | Batch 6S report and `backend/app/live_market_data/continuous.py` tests. | Demonstrate during live reconnect/restart and retain trace. |
| Duplicate, gap and out-of-order handling | PASS offline / PARTIAL live | Batch 6S replay and runtime tests; live trial had no opportunity to exercise all fault classes. | Capture live fault/recovery evidence or keep scope explicitly offline. |
| Detection to persisted opportunity | PASS diagnostic | Checkpoint03 and Batch6Q reports; genuine retained dataset, not fabricated. | Repeat under production authentication and live runtime conditions. |
| Authenticated browser/API experience | PARTIAL | Clerk negative tests and local demo UI; production Clerk session unavailable. | Authorized Clerk development credentials and browser session test. |
| User/tenant isolation | BLOCKED for production proof | Paper tracking is restricted to configured actor; no approved tenant topology/credentials. | Decide and test documented user/organization isolation model. |
| Model artifact and confidence | BLOCKED | No approved BTCUSDT/5m artifact; APIs correctly report unavailable. | Gate 6 research, independent evaluation and artifact approval. |
| Ranking | BLOCKED | Ranking/notification domains exist, but approved model-dependent score is absent. | Approved compatible artifact and unchanged ranking acceptance. |
| Outcome tracking/economics | BLOCKED | No approved predictive/economic evaluation. | Separate fee/spread/slippage/latency protocol and protected evaluation. |
| Durable notification queue | PASS isolated / NOT production-certified | Batch 6V PostgreSQL queue passed fenced multi-worker, retry, expiry, restart and migration tests. | Production migration review, provider adapter, opt-in policy, privacy/security review and explicit authorization. |
| External notifications | NOT ENABLED | Notification intents and queue delivery auditing are implemented/tested; no provider is configured. | Delivery provider, opt-in policy, retry audit, security review and explicit authorization. |
| Migrations and persistence | PASS disposable / NOT production-certified | Disposable migrations reached `20261003_0040`; no production DB was touched. | Gate 7 environment, backup/restore and migration evidence. |
| Redis rate limiting | PASS offline / production topology open | Atomic Redis limiter and outage tests pass; proxy identity policy remains undocumented. | Document trusted proxy topology and test spoofed-forwarded-header behavior. |
| Source/image provenance | BLOCKED | Source baseline is recorded; Gate 7 image certification remains blocked. | Exact certified build, immutable digest and byte-level source parity. |
| Monitoring/readiness | PARTIAL | Offline runtime health and truthful model-unavailable states exist. | Production monitoring, alerting, recovery and sustained live evidence. |
| Private beta | BLOCKED | Public/auth/model/operational prerequisites incomplete. | Explicit beta approval after critical/high defects are cleared. |
| Public launch | BLOCKED / NOT AUTHORIZED | Gate 6 and Gate 7 are not validated. | Independent Gate 6/Gate 7 approval and owner launch authorization. |

## Batch 6W private-local product

## Batch 6XY economic and thesis intelligence

| Requirement | Status | Evidence | Remaining requirement |
|---|---|---|---|
| Deterministic economic analysis | PASS locally | Decimal-safe evaluator, API/UI controls and focused tests. | No profitability or expected-value claim. |
| Persistent thesis identity and conservative grouping | PASS locally | Additive migrations, immutable originals, append-only events; 11 assessments surfaced as one ambiguous review cluster. | Validate policy with broader approved evidence. |
| Lifecycle and multi-hour monitoring | PARTIAL | Entry/missed/target/stop rules and timestamps implemented. | Complete multi-hour/live observation and outcome evidence. |
| Target extensions | NOT VALIDATED | Original targets remain immutable; no actionable extension displayed. | Separate research and approval. |
| INR/USD capital analysis | PASS locally | Explicit FX requirement and notional controls. | No live FX/account integration. |
| Gate 6/7 and public launch | BLOCKED | No approved artifact; protected evaluation and production evidence absent. | Independent approvals and owner launch authorization. |

| Requirement | Status | Evidence | Remaining requirement |
|---|---|---|---|
| Loopback frontend | PASS | `http://127.0.0.1:13003`; local owner mode rendered. | Keep private; no public exposure. |
| Genuine live BTCUSDT/5m worker | PASS for bounded local observation | Two finalized candles processed, checkpoint sequence 2, connected Binance public WebSocket. | Longer live stability remains separate from this bounded product batch. |
| Durable local persistence/restart | PASS | Local PostgreSQL `55448`; checkpoint retained across stop/start and advanced after restart. | Production-grade persistence remains a Gate 7 concern. |
| Model-dependent scoring/ranking | BLOCKED | API truthfully reports `unavailable_without_approved_artifact`. | Gate 6 research and approved artifact. |
| External notifications/trading | NOT ENABLED | Local handover explicitly disables both. | Separate authorization and provider/security review. |
| Local product usability | PASS | Dashboard shows real market status, runtime health and truthful no-candidate state. | Production Clerk/browser verification remains open. |

## Launch blockers that cannot be cleared by local code alone

1. The required full 24-hour live Binance observation has not been completed.
2. No approved BTCUSDT/5m predictive artifact exists.
3. Production Clerk credentials and a real authenticated browser test are unavailable.
4. Production deployment/image provenance, protected evaluation, economic validation and monitoring evidence remain outstanding.

