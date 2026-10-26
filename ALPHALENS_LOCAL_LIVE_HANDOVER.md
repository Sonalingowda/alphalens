# AlphaLens Local Live Handover

## Open the application

Open: **http://127.0.0.1:13003**

This is loopback-only local owner mode. It is not a public deployment and is not production Clerk authentication.

## Commands

Run from `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`:

```bash
backend/.venv/bin/python backend/scripts/local_stack.py start
backend/.venv/bin/python backend/scripts/local_stack.py status
backend/.venv/bin/python backend/scripts/local_stack.py stop
```

The stack uses persistent local state at `/private/tmp/alphalens-local-20261026` and does not use Batch 6U’s ports, database or Redis. Logs are:

```text
/private/tmp/alphalens-local-20261026/logs/api.log
/private/tmp/alphalens-local-20261026/logs/worker.log
/private/tmp/alphalens-local-20261026/logs/frontend.log
/private/tmp/alphalens-local-20261026/logs/postgres.log
/private/tmp/alphalens-local-20261026/logs/redis.log
```

Never print or share `runtime.env`; it contains disposable local credentials.

## What the owner can see

- Genuine Binance BTCUSDT/5m finalized-candle market status.
- Last finalized candle and worker/feed health.
- Current persisted detection opportunities when the unchanged Detection rules produce one.
- Entry, invalidation and target geometry for a persisted detection opportunity.
- Truthful empty/no-candidate state when none exists.
- Explicit model-unavailable state because no approved BTCUSDT/5m artifact exists.

The application does not show fabricated confidence, ranking, expected move, profitability or outcome data. External notifications and trading are disabled.

## Troubleshooting

- If `status` shows a dead process, run `stop`, then `start`; the local state directory is retained.
- If readiness is not `ready`, inspect `api.log`, `postgres.log` and `redis.log`.
- If the feed is stale or disconnected, inspect `worker.log` and confirm the Mac/network are available. The worker only accepts closed 5m candles and keeps its checkpoint fail-closed.
- Do not use ports `55446` or `56394`; those belong to the separately running Batch 6U trial.
- Do not delete the local state directory unless a separate cleanup decision is made; it contains the local database, checkpoint and evidence state.

## Current handover state

At handover, the local stack was running on ports `13003`, `18003`, `55448` and `56395`. The latest observed finalized candle was `2026-10-26T18:10:00Z`, with checkpoint sequence `2`, clear gap state and a connected public Binance WebSocket. The latest opportunity query returned no candidates and correctly reported the unavailable model artifact.

Gate 6 and Gate 7 remain blocked; this local handover does not authorize public launch.

## Batch 6Z observation state

The owner-facing stack remains on `http://127.0.0.1:13003/` with API `http://127.0.0.1:18003/`. A separate thesis-integrated six-hour observation is supervised on PostgreSQL `127.0.0.1:55458`, PID `34264`, with evidence under `/private/tmp/alphalens-batch6z-live-20261026`. It is currently IN PROGRESS and must not be confused with the owner-facing worker or Batch 6U.

The isolated worker accepts only finalized Binance BTCUSDT/5m candles, keeps trading and external notifications disabled, and reports model availability separately. Do not claim a six-hour PASS until the scheduled observation completes and its final report is reviewed.
