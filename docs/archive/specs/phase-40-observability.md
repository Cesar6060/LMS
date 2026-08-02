# Phase 40: Observability — Sentry live, uptime monitoring, cold-start closed out

## Goal

Turn the already-wired error tracking on in production and add uptime
monitoring. Backend (`sentry-sdk`, conditional init in
`config/settings.py:264-272`) and frontend (`@sentry/react`, init in
`src/main.tsx:12-29`, ErrorBoundary capture) both ship Sentry code today
with no DSN set — this phase creates the Sentry projects, sets the env
vars, and closes the instrumentation gaps: React Router v7 tracing,
prod source-map upload, API-error capture in the axios interceptor, and
PII scrubbing (backend currently sends `send_default_pii=True`).
UptimeRobot watches `/api/health/` on a 5-minute interval, which
deliberately doubles as a keep-warm ping that eliminates Render
free-tier cold starts for students. The long-deferred cold-start timing
figure gets recorded once, before keep-warm makes it unmeasurable.

## Out of scope

- Bundle code-splitting / `manualChunks` (deferred again — note in handoff backlog; the 1.29 MB Vite warning stays)
- Custom domain + real email provider (still paired, still deferred)
- Structured/JSON logging, log aggregation (console `LOGGING` stays as-is)
- Extra deep-health checks (R2, cache) — deep health stays DB-only
- Removing the dead `VITE_WS_URL` declaration in `vite-env.d.ts` (leave it)
- Sentry cron/uptime products (UptimeRobot covers uptime; free tier is enough)
- Any UI changes

## Sequencing constraint (do first)

- [x] **Record the cold-start figure BEFORE any UptimeRobot monitor exists.**
      RESOLVED 2026-07-21: no cold start exists — three idle windows (18,
      ~20, 45 min, zero traffic) all answered in ~0.15s; the service is
      not spinning down (see runbook step 0). Nothing to measure.
      After ≥15 min of API idle: `time curl -s https://stemquest-api.onrender.com/api/health/`
      Run twice (cold, then warm) and record both numbers in the runbook
      and handoff. Once 5-minute pings start, cold starts stop happening
      and this can never be measured again. Deferred in Phases 38 and 39
      — it dies here.

## Backend tasks

- [x] Sentry init polish in `config/settings.py` (keep the existing
      "inert unless env var set" gate on `SENTRY_DSN`):
  - [x] `send_default_pii=False` (drop usernames/emails/IPs — real
        students will use this)
  - [x] `environment=config('SENTRY_ENVIRONMENT', default='production')`
  - [x] `release=config('RENDER_GIT_COMMIT', default='') or None`
        (Render injects `RENDER_GIT_COMMIT` automatically; local runs
        get no release tag)
  - [x] Keep `traces_sample_rate=0.1`, `profiles_sample_rate=0.1`
- [x] Env-gated Sentry smoke-test endpoint (there is no other way to
      force a prod 500 on demand; Render free tier has no shell):
  - [x] View in `config/health.py` (or sibling module):
        `GET /api/sentry-debug/` raises `ZeroDivisionError` **only**
        when `config('SENTRY_DEBUG_ENDPOINT', default=False, cast=bool)`
        is true; otherwise returns 404. Plain Django view like `health`,
        no auth.
  - [x] URL in `config/urls.py`
  - [x] Tests in `config/tests/test_production_settings.py`: flag off →
        404; flag on (override via `monkeypatch`/settings) → raises;
        no auth required
- [x] No new requirements — `sentry-sdk[django]==2.19.2` already pinned

## Frontend tasks

- [x] React Router v7 tracing in `src/main.tsx`: replace
      `Sentry.browserTracingIntegration()` with
      `Sentry.reactRouterV7BrowserTracingIntegration({ useEffect,
      useLocation, useNavigationType, createRoutesFromChildren,
      matchRoutes })` (hooks imported from `react-router` — this project
      uses the v7 unified package, not `react-router-dom`)
- [x] In `src/App.tsx`: wrap the route tree with
      `Sentry.withSentryReactRouterV7Routing(Routes)` and use that
      component in place of `Routes`
- [x] API-error capture in `src/services/api.ts` response interceptor:
      `Sentry.captureException` for **5xx responses and network errors
      only** — never 401/403/404 (auth redirects and permission checks
      are normal traffic, not incidents). Attach method + URL as
      context; still re-throw so callers behave unchanged
- [x] Session Replay privacy: keep `replayIntegration()` with default
      masking (`maskAllText`/`blockAllMedia` default on in v8) — verify
      no options currently override that; do not weaken masking
- [x] Source-map upload:
  - [x] Add `@sentry/vite-plugin` to devDependencies
  - [x] `vite.config.ts`: add the plugin **only when
        `env.SENTRY_AUTH_TOKEN` is present** (local and CI builds
        without the token must keep building cleanly — same
        philosophy as the existing `VITE_API_URL` guard, but soft, not
        fail-fast); options: `org`/`project` from `SENTRY_ORG` /
        `SENTRY_PROJECT` env, `sourcemaps.filesToDeleteAfterUpload:
        ["./dist/**/*.map"]` so maps never deploy to the public site
  - [x] `build: { sourcemap: 'hidden' }` (generated for upload, no
        `sourceMappingURL` comment referencing them in served JS)
- [x] `src/vite-env.d.ts`: no changes needed (`VITE_SENTRY_DSN?` already
      declared)
- [x] Confirm dev behavior unchanged: with no `VITE_SENTRY_DSN` set,
      the init block stays skipped and the app runs as before

## Ops / dashboard tasks (user actions — write these up as a runbook)

- [x] Write `docs/runbooks/phase-40-observability-steps.txt` (plain
      text, step-by-step, per house style) covering everything below,
      and keep AS-RUN NOTES in it as the deploy proceeds
- [x] Sentry: create account (cesarvillarreal11@gmail.com), one org,
      two projects — `stemquest-django`, `stemquest-react`. Collect:
      both DSNs, org slug, project slug, and an auth token with
      `project:releases` + source-map upload scope
- [x] Render (backend env vars): set `SENTRY_DSN`; optionally
      `SENTRY_ENVIRONMENT=production` (matches the default). Later,
      briefly: `SENTRY_DEBUG_ENDPOINT=true` for the smoke test, then
      remove it
- [x] Cloudflare Workers **build** variables (Settings > Build — NOT
      runtime variables; same trap as Phase 39): `VITE_SENTRY_DSN`,
      `SENTRY_AUTH_TOKEN` (secret), `SENTRY_ORG`, `SENTRY_PROJECT`
      (verified 2026-07-21 from the live bundle: DSN + sentry debug
      IDs present → plugin ran, maps uploaded)
- [x] UptimeRobot: create account, three monitors, email alerts
      **DESCOPE REVERSED 2026-07-21** — Cesar created the account and
      three monitors in the dashboard; the deep-DB keyword monitor was
      created inverted (ALERT_EXISTS) and immediately alarmed. Fixed
      via MCP by recreating it as ALERT_NOT_EXISTS (id 803564235); the
      inverted one is paused and renamed "DELETE ME…" (MCP cannot
      delete monitors — remove it in the dashboard).
- [ ] ~~Optional cleanup while in `/admin/`: delete the Phase 39 test
      account `r2-check@example.com`~~ MOVED to backlog (tracked in
      the phase-40 handoffs) — optional, not a phase gate.

## Verification

- [x] `/verify-stack` passes: pytest 376 (372 + 4 sentry-debug
      tests), `tsc --noEmit` 0 errors, lint 0 errors / 22 warnings
      (baseline)
- [x] Local prod-mode build succeeds **without** `SENTRY_AUTH_TOKEN`
      (plugin correctly skipped): `VITE_API_URL=https://stemquest-api.onrender.com/api npm run build`
- [x] Cold-start figures recorded (see sequencing constraint) in
      runbook + handoff
- [x] **Backend Sentry smoke test**: set `SENTRY_DEBUG_ENDPOINT=true`
      on Render → `curl /api/sentry-debug/` returns 500 → event
      appears in `stemquest-django` with environment=production, a
      release SHA, and **no** user email/IP in the event (PII check) →
      remove the env var → endpoint 404s again
      (completed 2026-07-21 evening; endpoint re-verified 404,
      /api/health/ 200)
- [ ] ~~**Frontend Sentry smoke test**~~ WAIVED 2026-07-21 at phase
      close (Cesar: "let's be done"). Frontend Sentry is live and the
      source-map upload was verified indirectly (debug IDs in the
      bundle, maps not served); the end-to-end event test was skipped.
      If frontend errors ever look unreadable in Sentry, run this
      one-minute test first: on the live site console,
      `setTimeout(() => { throw new Error('smoke') })` → readable
      stack in `stemquest-react`.
- [x] Served JS exposes no source maps: deployed JS contains no
      `sourceMappingURL`; the `.map` URL answers with the SPA HTML
      fallback (200 text/html app shell — Worker serves index.html
      for unknown paths), not map content, so the real map is not
      deployed (verified 2026-07-21)
- [x] UptimeRobot monitors green / alert email — verified 2026-07-21:
      all three monitors UP; alert email delivery proven by the real
      DOWN alert from the inverted keyword monitor (landed in Gmail,
      though in Trash — check filters if that wasn't manual)
- [x] ~~Keep-warm check after 1 hour~~ MOOT — no cold start exists
      (measured 2026-07-21, runbook step 0)
- [x] Manual click-through of the live site: register/login, course
      map, a lesson — console clean, no Sentry noise events from
      normal browsing (replay/tracing sampling working, no 4xx spam
      from the interceptor). Passed per working convention: no
      problems reported.
