# Checkpoint 04G — bounded Binance warmup evidence

This record contains sanitized acceptance evidence only. The runtime
checkpoint file and database remain outside source control.

## Acquisition

- Source: `https://data-api.binance.vision/api/v3/klines`
- Symbol: `BTCUSDT`
- Interval: `5m`
- Limit: `240`
- Request boundary: exclusive `endTime`, one millisecond before the latest
  completed 5-minute boundary
- UTC window: `2026-11-10T16:00:00Z` through `2026-11-11T12:00:00Z`
- Finalized candle count: `240`
- Contiguous open range: `2026-11-10T16:00:00Z` through
  `2026-11-11T11:55:00Z`

## Acceptance

- Lineage: `binance-btcusdt-5m-04g-ecaa35ea-f52e-45a2-882f-53ebbeefb26f`
- Batch: `559d9dff-2965-5a37-8a4d-095a3e631eba`
- State: `ACCEPTED`
- Batch members: `240`
- Source response SHA-256:
  `f2fdebc9d8b89052d4f08fcece4b2c946f99f27eaca72f44eef105c515209d72`
- Membership SHA-256:
  `223645b2391d2952c53bdee41ae18d20d40cf93fd4493f20ff4c7e92eac72a01`
- Batch SHA-256:
  `eaa0107ba999d5bc130633f52329ab2503592821cbaa08c7b0994a6c0524210e`

The batch was persisted through the approved single-transaction repository
path. The post-commit checkpoint was written afterward. PostgreSQL contained
240 immutable market snapshots, one accepted batch, and 240 members; no
opportunities or paper-tracking records were created.

## Verification

- `/markets/live`: HTTP 200 with the latest genuine Binance snapshot.
- Frontend: rendered `Snapshot available`.
- Dashboard: rendered `API ready · model unavailable`.
- Backend readiness: HTTP 200.
- Model health: HTTP 503 `ARTIFACT_UNAVAILABLE`.
- Protected unauthenticated request: HTTP 401.
- Approved CORS preflight: HTTP 200.
- Disallowed CORS origin: HTTP 400 without `Access-Control-Allow-Origin`.
- No Binance worker, predictive worker, or trading process was started.

This bounded acquisition does not authorize continuous ingestion, predictive
model activation, trading, deployment, or protected-test access.
