# AlphaLens Gate 8B Localhost Demo Runbook

## Verified demo

- Frontend: http://localhost:13023/local-login
- Dashboard: http://localhost:13023/
- Live Market: http://localhost:13023/markets/live
- Backend: http://127.0.0.1:18023
- Database: owner-local PostgreSQL on `127.0.0.1:55461`
- Worker: intentionally stopped for the read-only demo
- Verified source: Binance BTCUSDT/5m, source digest `6f844a74e89537ff26c7195e895416b42bb78a31a01618eb3d1e44e3b09210c5`

The accepted six-hour evidence is preserved at:

`/private/tmp/alphalens-six-hour-acceptance-retry-20261103T121931Z`

Do not start a market worker during this demo.

## Demo flow

1. Open `/local-login` and enter the locally stored owner token. Never paste the token into chat or logs.
2. Open the dashboard.
3. Confirm the prominent stopped-feed warning, zero Active opportunities, and `Model unavailable` status.
4. Open Monitoring and History. Historical records must remain non-actionable while the feed is stopped.
5. Open Recent Opportunities and select an `Open record` link.
6. Show the immutable entry/stop/target geometry, lifecycle state, evidence references, and limitations. Do not describe `INITIAL_TARGET_REACHED` as profitability or a filled trade.
7. Open Live Market and show the completed Binance candle snapshot. It is historical persisted evidence while the worker is stopped.
8. Open the mobile navigation at narrow width and verify Dashboard, Opportunities, and Live Market navigation.

## Expected truth states

- `/health` returns `503 ARTIFACT_UNAVAILABLE` because no approved predictive artifact is installed.
- Active opportunities: `0` while the feed is stopped.
- History endpoint: genuine terminal thesis outcomes from persistent thesis tables.
- Live Market: completed candles only; no fabricated or mock candles.
- No confidence, win-rate, profitability, or predictive-validation claim is available.

## Safe startup check

The verified stack is already running. Before starting anything, confirm ownership:

```sh
lsof -nP -iTCP:13023 -sTCP:LISTEN
lsof -nP -iTCP:18023 -sTCP:LISTEN
pgrep -af 'local_market_worker|run_market_acceptance|caffeinate.*alphalens'
```

Only the integration worktree may own ports `13023` and `18023`. Do not use
`backend/scripts/local_stack.py` for this demo; it creates a separate local
database rather than reopening the accepted owner database.

If a controlled restart is required, source the private runtime environment
without printing it, set the database and Redis endpoints to ports `55461` and
`56398`, set `ALPHALENS_LOCAL_RUNTIME_STATUS_PATH` to the preserved acceptance
`state/worker-status.json`, and start only the backend/frontend from this
worktree. Keep `ALPHALENS_MARKET_DATA_STARTUP_ENABLED=false`.

## Shutdown

Stop only processes proven to belong to this worktree and this demo:

```sh
ps -p <integration-backend-pid> -o pid=,command=
ps -p <integration-frontend-pid> -o pid=,command=
kill -TERM <integration-backend-pid> <integration-frontend-pid>
```

Do not stop the PostgreSQL or Redis services unless the owner explicitly wants
the whole localhost stack shut down. No database reset or checkpoint change is
part of demo shutdown.

## Troubleshooting and fallback

- `401` at `/`: authenticate through `/local-login`.
- `503 ARTIFACT_UNAVAILABLE` at `/health`: expected; keep the model-unavailable state visible.
- API timeout: verify that port `18023` belongs to this worktree and that PostgreSQL/Redis remain available.
- External Binance connectivity failure: do not start or repair ingestion. Use the preserved completed-candle snapshots and historical thesis evidence, and show the stopped-feed warning.
- If persisted history is unavailable, stop the demo rather than substituting mock data.

This runbook supports a read-only operational demonstration. It does not establish
predictive accuracy, profitability, or model validation.
