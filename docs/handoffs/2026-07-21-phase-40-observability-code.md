# Handoff: Phase 40 code complete — Sentry wired, ops steps pending

## Current state

All Phase 40 **code** is done on `feat/phase-40-observability`
(commit `9bb1718`), verified green. The observability stack is now
fully wired but **inert until Cesar does the dashboard work** — Sentry
projects, env vars, and UptimeRobot monitors, all scripted step-by-step
in `docs/runbooks/phase-40-observability-steps.txt`.

- **Backend** (`config/settings.py:264-277`): Sentry init now sends
  `send_default_pii=False` (students' emails/IPs stay out of events),
  tags `environment` (from `SENTRY_ENVIRONMENT`, default `production`)
  and `release` (from Render-injected `RENDER_GIT_COMMIT`; `None`
  locally). Still inert unless `SENTRY_DSN` is set.
- **Smoke-test endpoint**: `GET /api/sentry-debug/` raises
  `ZeroDivisionError` only when `SENTRY_DEBUG_ENDPOINT=true` (read
  per-request, so flipping the Render env var is enough); otherwise
  404. Plain Django view in `config/health.py`, no auth — it exists
  because Render free tier has no shell, so this is the only way to
  force a prod 500. Four guard tests in
  `config/tests/test_production_settings.py`.
- **Frontend tracing**: `main.tsx` uses
  `reactRouterV7BrowserTracingIntegration` (hooks from `react-router`,
  `useEffect` from React); `App.tsx` renders through
  `SentryRoutes = Sentry.withSentryReactRouterV7Routing(Routes)` so
  transactions get parameterized route names.
- **API-error capture** (`src/services/api.ts`): the response
  interceptor now `Sentry.captureException`s **5xx and network errors
  only** — 401/403/404 and canceled requests never reach Sentry.
  Method/URL/status attached as context; errors still re-thrown.
- **Source maps**: `@sentry/vite-plugin` (devDependency) runs **only
  when `SENTRY_AUTH_TOKEN` is present** (soft gate — local/CI builds
  stay tokenless and clean); `build.sourcemap: 'hidden'` so served JS
  carries no `sourceMappingURL`; uploaded maps are deleted from
  `dist/` before deploy.
- Session Replay masking left at v8 defaults (verified no overrides).

## Verification evidence (2026-07-21)

- `/verify-stack` PASS: pytest **376** (372 + 4 sentry-debug),
  tsc 0 errors, lint 0 errors / 22 warnings (baseline).
- Tokenless prod build proven:
  `VITE_API_URL=… npm run build` succeeds with no Sentry env vars;
  `dist/assets/*.js.map` generated; `grep -c sourceMappingURL` on the
  bundle → 0.
- **Cold-start figure (finally recorded, before any keep-warm monitor
  exists)**: COLD_PLACEHOLDER — see runbook step 0.

## Gotchas (re)discovered

- The rollup darwin-arm64 gotcha struck again: any `npm install` on
  the host regenerates `node_modules` and drops the mac binary —
  `npm install --no-save @rollup/rollup-darwin-arm64` fixes the build.
- `frontend/tsconfig.tsbuildinfo` shows as modified but hasn't been
  committed since Phase 14 — left out of the commit on purpose.

## Not done (all user dashboard actions, runbook steps 1–9)

1. Merge the PR from `feat/phase-40-observability`.
2. Sentry account/org + `stemquest-django` / `stemquest-react`
   projects; collect DSNs, org slug, auth token.
3. Render: `SENTRY_DSN` env var; later `SENTRY_DEBUG_ENDPOINT=true`
   briefly for the smoke test, then remove.
4. Cloudflare Workers **build** variables (same trap as Phase 39 —
   NOT runtime vars): `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`,
   `SENTRY_ORG`, `SENTRY_PROJECT`.
5. UptimeRobot: 3 monitors (shallow health @5min = keep-warm, deep
   keyword @60min, frontend @5min) + alert-email proof.
6. Both Sentry smoke tests + PII check, source-map 404 check,
   keep-warm confirmation, final click-through.
7. Optional: delete `r2-check@example.com` in `/admin/`.

## Backlog (unchanged)

- Bundle code-splitting (1.29 MB warning) — deferred again.
- Custom domain + real email provider — still paired, still deferred.
- Local dev frontend container still has the stale pre-recharts
  `node_modules` volume (Phase 38 leftover).

## Files to read first

- `docs/runbooks/phase-40-observability-steps.txt` — every remaining
  step, in order
- `docs/specs/phase-40-observability.md` — checklist; code items
  ticked, ops items open
