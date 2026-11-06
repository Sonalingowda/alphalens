# AlphaLens ETHGlobal Clerk Recovery Status

Status: BLOCKED pending alignment of the existing Clerk Development instance.

## Isolated source

- Worktree: `/Users/sonalingowda/alphalens-rebuild-20261105`
- Branch: `gate9d2/owner-infrastructure-20261105`
- Baseline HEAD before this documentation commit: `206599287ba1ccfbe87bc3b0db5b761c7a1e8926`
- Protected Downloads checkout and forensic artifacts were not modified.

## Verified local foundation

- PostgreSQL: `127.0.0.1:55461`, fresh owner database, Alembic `20261027_0043`.
- Redis: authenticated on `127.0.0.1:56397`.
- Database remains empty; no market candles, opportunities, assessments, or lifecycle events were added.
- Backend readiness passed on `127.0.0.1:18000`.
- Unauthenticated protected paper-tracking requests return HTTP 401.
- Gate 6 remains fail-closed because no approved production artifact is present.

## Clerk checks

- Existing Development credentials are present only in ignored mode-600 local configuration.
- Publishable and secret key formats are valid.
- Authorized user exists in the backend-secret instance.
- Frontend publishable-key metadata does not match the backend-secret instance.
- `http://localhost:3000` is not currently listed as an allowed origin on the backend-secret instance.
- No credential values, tokens, or user secrets are recorded here.

## Runtime boundary

- Frontend was not left running while Clerk instance alignment was failing.
- No ingestion, worker, daily supervisor, checkpoint creation, Binance acquisition, deployment, or public exposure occurred.

## Required next action

Use the existing Clerk Development instance associated with the backend secret. Copy its matching publishable key into the ignored frontend configuration and add `http://localhost:3000` to that same instance's allowed origins. Re-run non-secret alignment checks before starting the frontend.
