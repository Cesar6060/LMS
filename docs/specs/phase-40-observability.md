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
- [ ] Sentry: create account (cesarvillarreal11@gmail.com), one org,
      two projects — `stemquest-django`, `stemquest-react`. Collect:
      both DSNs, org slug, project slug, and an auth token with
      `project:releases` + source-map upload scope
- [ ] Render (backend env vars): set `SENTRY_DSN`; optionally
      `SENTRY_ENVIRONMENT=production` (matches the default). Later,
      briefly: `SENTRY_DEBUG_ENDPOINT=true` for the smoke test, then
      remove it
- [ ] Cloudflare Workers **build** variables (Settings > Build — NOT
      runtime variables; same trap as Phase 39): `VITE_SENTRY_DSN`,
      `SENTRY_AUTH_TOKEN` (secret), `SENTRY_ORG`, `SENTRY_PROJECT`
- [ ] UptimeRobot: create account, three monitors, email alerts on:
  - [ ] `https://stemquest-api.onrender.com/api/health/` — every
        **5 min** (SHALLOW on purpose: it never touches the DB, so it
        keeps Render warm without keeping Neon's compute awake —
        health.py was written for exactly this)
  - [ ] `https://stemquest-api.onrender.com/api/health/?deep=1` —
        keyword monitor for `"database": "ok"`, every **60 min** (DB
        alerting; ~24 brief Neon wakes/day is negligible compute)
  - [ ] `https://stemquest.cesarvillarreal11.workers.dev/` — every 5 min
- [ ] Optional cleanup while in `/admin/`: delete the Phase 39 test
      account `r2-check@example.com`

## Verification

- [x] `/verify-stack` passes: pytest 376 (372 + 4 sentry-debug
      tests), `tsc --noEmit` 0 errors, lint 0 errors / 22 warnings
      (baseline)
- [x] Local prod-mode build succeeds **without** `SENTRY_AUTH_TOKEN`
      (plugin correctly skipped): `VITE_API_URL=https://stemquest-api.onrender.com/api npm run build`
- [x] Cold-start figures recorded (see sequencing constraint) in
      runbook + handoff
- [ ] **Backend Sentry smoke test**: set `SENTRY_DEBUG_ENDPOINT=true`
      on Render → `curl /api/sentry-debug/` returns 500 → event
      appears in `stemquest-django` with environment=production, a
      release SHA, and **no** user email/IP in the event (PII check) →
      remove the env var → endpoint 404s again
- [ ] **Frontend Sentry smoke test**: on the live site, in the browser
      console run `setTimeout(() => { throw new Error('phase-40 smoke') })`
      (Sentry's global handlers catch uncaught errors — no code change
      needed) → event appears in `stemquest-react` with a **readable,
      source-mapped stack trace** (proves the upload worked) and the
      route name from router instrumentation
- [ ] Served JS exposes no source maps: `curl` a deployed asset URL
      with `.map` appended → 404; deployed JS contains no
      `sourceMappingURL` pointing at a map
- [ ] UptimeRobot: all three monitors green; deep monitor shows the
      keyword match; alert email confirmed deliverable (temporarily
      point a scratch monitor at a known-404 path, receive the email,
      delete it)
- [ ] After ~1 hour of monitors running: hit the API after 20+ min of
      no manual traffic and confirm response is instant (keep-warm
      works)
- [ ] Manual click-through of the live site: register/login, course
      map, a lesson — console clean, no Sentry noise events from
      normal browsing (replay/tracing sampling working, no 4xx spam
      from the interceptor)
