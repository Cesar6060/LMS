# Phase 49 — Move the API to Virginia (co-locate with Neon)

**Status: PLANNED (2026-07-22) — not started.** Operator steps live in
`docs/runbooks/phase-49-region-move-steps.txt`.

## Goal

Recreate `stemquest-api` in Render's Virginia region so the Django API sits
next to Neon Postgres (aws-us-east-1) instead of across the country in
Oregon. Measured on the live service (Phase 48): shallow `/api/health/`
~130–250 ms vs deep `?deep=1` ~250–370 ms — every DB round trip pays
~70–130 ms of pure geography, multiplied by queries per request. After the
move, deep health should land within ~20 ms of shallow.

## Hard constraints (why this is a recreation, not a setting)

- Render cannot change a service's region in place — a new service must be
  built in Virginia and traffic cut over.
- The clean URL is not reclaimable: new Render services get a
  random-suffixed slug (observed: `cesar-portfolio-erwh.onrender.com`), so
  the new service WILL have a new URL — plan every consumer of
  `https://stemquest-api.onrender.com` into the cutover.
- The old SECRET_KEY lives only in Render's vault (generateValue) and
  cannot be read out → the new service gets a fresh key. SIMPLE_JWT signs
  with SECRET_KEY and password-reset tokens are keyed on it, so at cutover
  all live sessions and in-flight reset links die. Accepted: users
  re-login (demo users just click demo login again).
- Dashboard is the single source of truth (Phase 48): every env var must be
  re-entered by hand on the new service. The names-only inventory at the
  bottom of `render.yaml` is the checklist.

## Consumers of the API URL (complete list, verified 2026-07-22)

| Consumer | Change |
|----------|--------|
| `frontend/public/_headers` CSP `connect-src` | PR: add the new origin (keep the old one during the rollback window) |
| Cloudflare `VITE_API_URL` build var | Dashboard: point at `https://<new-host>/api`, redeploy frontend |
| UptimeRobot monitor 803564203 (shallow health) | Update URL |
| UptimeRobot monitor 803564235 (deep-health keyword) | Update URL |
| `README.md` line 8 (API link) | PR |
| `frontend/vite.config.ts` error-message example | PR (cosmetic) |
| New service's own `ALLOWED_HOSTS` | Set to the new host once Render assigns it |

`CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` / `FRONTEND_URL` copy over
unchanged — the frontend URL doesn't move. Neon, R2, and Gmail are all
region-agnostic; there is NO data migration.

## Out of scope

- Custom domain. It would make this the last URL-breaking migration ever
  (all consumers would point at a stable name), but it needs a purchased
  domain — worth deciding before the *next* infra move, not blocking this
  one.
- Any schema/data work — same Neon database throughout.
- Old-spec/runbook history mentioning the old URL (historical record).

## Plan (detail in the runbook)

- [x] **A. Prepare.** Collect every secret to re-enter: DATABASE_URL (Neon
      console), Gmail app password (mint a new one if not saved),
      DEMO_ACCOUNT_PASSWORD, ADMIN_URL, R2 keys, SENTRY_DSN (if set).
      Merge nothing yet.
- [x] **B. Build + verify the new service in Virginia** (old service keeps
      serving): New → Web Service (NOT Blueprint) from `Cesar6060/LMS`,
      region Virginia, plan Starter, shape per `render.yaml`; enter all
      env vars; note the assigned URL; set ALLOWED_HOSTS; verify directly
      against the new URL — shallow+deep health, admin, demo-login curl,
      reset-email round trip, R2 media, and the latency win (deep ≈
      shallow).
- [ ] **C. Cut over.** Merge the PR adding the new origin to the CSP (+
      README/vite.config touch-ups); flip `VITE_API_URL` in Cloudflare and
      redeploy the frontend; full click-through on the live site; update
      both UptimeRobot monitor URLs.
- [ ] **D. Decommission.** Suspend the old Oregon service (instant
      rollback stays possible); after a clean rollback window (~3 days,
      watching UptimeRobot), delete it to stop double Starter billing
      (~$7/mo each while both run); cleanup PR drops the old origin from
      the CSP and updates `render.yaml`'s documented region/service id.

## Rollback (any time before D completes)

Flip `VITE_API_URL` back and redeploy the frontend (old origin is still in
the CSP), resume the old service if suspended, repoint the UptimeRobot
monitors. The old service is untouched until step D.

## Verification

- [x] New service: `/api/health/?deep=1` 200 with deep latency within
      ~20 ms of shallow (run 5 samples of each). *(2026-07-22: shallow
      ~0.11-0.22 s, deep ~0.12-0.19 s after first-connection warmup —
      Oregon's +70-130 ms DB penalty is gone. Service
      stemquest-api-va.onrender.com / srv-d9go1em1a83c73f50r2g; NOTE:
      Render granted the clean name, no random suffix.)*
- [ ] Live click-through post-cutover: demo login, course roadmap, media
      loads (R2 presigned), reset email round trip, no CSP/CORS errors in
      the console.
- [x] Throttles fire on the new service (30-burst at demo-login →
      20×200 / 10×429 pattern for 10/min × 2 workers). *(2026-07-22:
      exactly 20 allowed then 429s; SMTP reset request 200, logs clean.)*
- [ ] UptimeRobot both monitors UP against new URL.
- [x] `/verify-stack` green on the cutover PR (CSP/README changes).
      *(2026-07-22: 425 passed, tsc 0 errors, lint 0/22 baseline — PR #44,
      merged; CI green.)*
- [ ] Old service deleted; billing shows a single Starter instance.
