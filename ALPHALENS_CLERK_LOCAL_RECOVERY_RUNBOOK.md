# AlphaLens Clerk Local Recovery Runbook

Status: checkpoint 01 — local Clerk/browser recovery is partially verified.

## Scope

- Worktree: `alphalens-rebuild-20261105`
- Frontend: `http://localhost:3000`
- Backend: `http://127.0.0.1:18000`
- Clerk target: existing Development instance `ins_3K02Ot7jF7nuQkuGpvMrFnz2Awa`
- Gate 6 remains fail-closed; Binance ingestion, workers, checkpoints,
  supervisors, inference and trading remain disabled.

## Configuration contract

Frontend runtime sources are read by Next.js according to its normal local
environment precedence. The browser-visible values are
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and
`NEXT_PUBLIC_ALPHALENS_API_BASE_URL`. Server-only values include
`ALPHALENS_API_BASE_URL` and, where required by the installed Clerk
integration, `CLERK_SECRET_KEY`. The backend uses
`ALPHALENS_CLERK_SECRET_KEY`, `ALPHALENS_CLERK_AUTHORIZED_USER_ID`, and
`ALPHALENS_CLERK_AUTHORIZED_PARTIES`.

Never commit `.env.local`, `.env`, runtime environment files, secret values,
session material, or full environment dumps. The publishable key may be sent
to the browser; Clerk secret keys must remain server-side and must never be
passed as build arguments or copied into frontend artifacts.

The container runtime uses:

- server-side API base: `http://host.docker.internal:18000`;
- browser API base: `http://127.0.0.1:18000`;
- host publication: `127.0.0.1:3000:3000` only.

The backend remains host-loopback bound. Docker Desktop host-gateway access
was verified without changing the backend bind address.

## Verified checkpoint evidence

- Frontend container routes `/` and `/markets/live` returned HTTP 200.
- Container health was healthy with zero restarts and host mapping restricted
  to `127.0.0.1:3000`.
- LAN access to `192.168.0.101:3000` was refused.
- Backend readiness returned HTTP 200.
- Unauthenticated protected requests returned HTTP 401.
- `/health` returned the expected HTTP 503 `ARTIFACT_UNAVAILABLE`.
- Browser visually showed the Clerk user avatar; authenticated protected API
  success was not claimed.

## Known limitation and correction

Protected browser requests use Clerk's session token and therefore require a
CORS preflight. The API audit stream accepts application `GET`/`POST` only;
preflight `OPTIONS` requests must pass through CORS without entering that
stream. The local correction is in `backend/app/api/application.py`.

The correction passed the targeted prediction API suite. Live authenticated
verification still requires the approved backend runtime environment and a
real owner browser session. No auth bypass is permitted.

## Safe verification

Run targeted backend tests from `backend/` with `PYTHONPATH=.`. Confirm the
backend listens only on `127.0.0.1:18000`, the frontend container publishes
only `127.0.0.1:3000`, readiness is 200, `/health` preserves
`ARTIFACT_UNAVAILABLE`, and unauthenticated protected requests remain 401.
Complete real Clerk sign-in before testing an authenticated protected request.

## Rollback

Revert the checkpoint commit if the code correction must be removed. Stop and
remove only the disposable frontend container, then remove its local image if
desired. Do not remove PostgreSQL, Redis, source files, recovery evidence, or
unrelated containers. Restore runtime configuration only from the owner's
approved private source; never reconstruct or rotate credentials here.
