# Handoff: Phase 40 — Sentry live on backend, phase closed early by choice

## Current state

PR **#29** (all Phase 40 code) is **merged to main** with green CI, and
both hosts have redeployed from it. Cesar decided to stop the
observability phase partway through the ops checklist — deliberately,
not by accident. What that leaves:

- **Backend Sentry: LIVE (but never smoke-tested).** `SENTRY_DSN` is
  set on Render and the merged code sends `send_default_pii=False`
  (student emails/IPs scrubbed), `environment=production`, and the
  deploy SHA as `release`. NOTE: prod briefly ran the *old*
  `send_default_pii=True` init between Cesar setting the DSN and the
  merge — closed now.
- **Smoke-test endpoint deployed**: `GET /api/sentry-debug/` 404s
  unless `SENTRY_DEBUG_ENDPOINT=true` is set on Render; then it raises
  `ZeroDivisionError`. Runbook step 6 (the 5-minute verification that
  events actually reach Sentry) has NOT been run — strongly
  recommended before trusting the pipeline.
- **Frontend Sentry: dormant.** Cesar stopped before step 4, so
  `VITE_SENTRY_DSN` / `SENTRY_AUTH_TOKEN` were never added to the
  Cloudflare build. All the frontend code (router-v7 tracing,
  `SentryRoutes`, 5xx-only axios capture, gated source-map plugin) is
  merged and no-ops cleanly without the env vars.
- **UptimeRobot: descoped** ("probably not going to implement").
  Consequences accepted: no down alerts, deep DB check unwatched.
- **Cold-start question: RESOLVED, surprisingly.** Three measurement
  attempts (idle windows of 18, ~20, and 45 minutes with zero traffic
  from us) all answered in ~0.15s — **the service is not spinning
  down at all**, so there is no cold start to measure and no
  keep-warm need. Probable causes: Render probing render.yaml's
  `healthCheckPath`, and/or ambient bot traffic to the public
  onrender.com hostname. Details in runbook step 0. The three-phase
  "record the cold-start figure" chore dies here, answered.

## Verification evidence (2026-07-21)

- `/verify-stack` PASS pre-merge: pytest **376** (372 + 4 sentry-debug
  guard tests), tsc 0 errors, lint 0 errors / 22 warnings (baseline).
- CI green on PR #29 (both jobs), merged same day.
- Tokenless prod build proven: map generated, `grep -c
  sourceMappingURL` on the bundle → 0.

## NEXT SESSION: portfolio polish (Cesar's stated priorities)

1. **Update the README** — present the project for portfolio viewers
   (what it is, the live URL, the stack, screenshots).
2. **Demo account for visitors**: `jdoe@demo.com` / `Admin123!` so
   curious people can log in and click around without registering.
   Design decisions to make when building it:
   - Make it a **plain student or instructor account, NEVER a
     superuser** — the credentials will be public in the README.
   - Enroll it in JAVA101 with some progress/grades so the app looks
     alive, not empty.
   - Consider that anything this account writes (discussion posts,
     avatar) is world-editable; a periodic reset (management command
     or cron) may be worth it eventually.

## Also still open (older backlog, in impact order)

1. **Email doesn't send in prod** — `EMAIL_BACKEND` defaults to the
   console backend, so password-reset/verification emails go to
   Render logs, not inboxes. Biggest functional gap before real
   students. Paired with the custom-domain item.
2. **DB backups** — Neon free tier keeps only a short restore window;
   an occasional `pg_dump` is cheap insurance once real grades exist.
3. Runbook steps 4–7 if frontend Sentry is ever wanted (15 min).
4. Delete `r2-check@example.com` via `/admin/` (Phase 39 leftover).
5. Bundle code-splitting (1.29 MB warning) — deferred again.
6. Local dev: stale pre-recharts `node_modules` volume (Phase 38).

## Gotchas from this session

- The rollup darwin-arm64 gotcha struck again: any host `npm install`
  drops the mac binary — fix is
  `npm install --no-save @rollup/rollup-darwin-arm64`.
- Runbook steps got executed out of order (dashboard steps 2–3 before
  the PR existed); harmless but it polluted cold-start attempt 1 and
  briefly ran PII-unsafe Sentry init in prod. Sequencing notes are in
  the runbook AS-RUN section.
- `frontend/tsconfig.tsbuildinfo` churns but hasn't been committed
  since Phase 14 — leave it out of commits.

## Files to read first

- `docs/runbooks/phase-40-observability-steps.txt` — what ran, what
  didn't, AS-RUN notes (including the descope)
- `docs/specs/phase-40-observability.md` — checklist: code all ticked,
  ops items open/descoped
- `docs/deployment-tools.txt` — NEW: plain-language reference for
  every tool in the deployment (useful source for the README rewrite)
