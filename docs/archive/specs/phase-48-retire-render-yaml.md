# Phase 48 — Retire render.yaml as prod config source

## Goal

Make the repo stop lying about how production is configured. The render.yaml
Blueprint's env-var sync has been silently broken since ~the repo migration
to `Cesar6060/LMS`: values declared in render.yaml (`EMAIL_*`, `THROTTLE_*`,
…) never reached the service and had to be hand-entered in the Render
dashboard during the Phase 46/47 rollouts. The service itself is fine — it
deploys directly from `Cesar6060/LMS@main` with auto-deploy on, so the
Blueprint adds nothing that works.

Decision (2026-07-22, user-confirmed): **retire render.yaml as a config
source** rather than reconnect the Blueprint. Reconnecting was rejected
because a successful sync of today's file would try to apply `plan: free`
— downgrading the service and re-breaking outbound SMTP (Render free tier
blocks all SMTP egress, the Phase 47 discovery that forced the Starter
upgrade).

After this phase: the **Render dashboard is the single source of truth** for
every service env var, and render.yaml documents the service shape only.

## Findings this phase is based on (verified 2026-07-22 via render CLI)

- Service `stemquest-api` (`srv-d9fdm3jh523c73f0rlkg`): repo
  `Cesar6060/LMS`, branch `main`, autoDeploy yes — code deploys don't
  involve the Blueprint.
- Dashboard startCommand **matches** render.yaml exactly
  (`gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2
  --timeout 120`) — the handoff's open confirmation item.
- Drift: dashboard plan is **starter** (render.yaml said `free`); actual
  region is **oregon** (render.yaml said `virginia` and claimed Neon
  co-location).

## Out of scope

- Region move (Oregon → Virginia to co-locate with Neon aws-us-east-1).
  Measured 2026-07-22: shallow `/api/health/` ~130–250 ms vs deep
  `?deep=1` ~250–370 ms — each DB round trip pays ~70–130 ms
  cross-country, multiplied by queries per request. Real speedup
  available, but Render can't migrate regions in place; it means
  recreating the service (re-enter all dashboard secrets, re-point the
  frontend if the URL changes). **Phase 49 candidate.**
- Deleting render.yaml outright — it stays as service-shape documentation.
- Any change to the running service or its dashboard env vars (this phase
  is repo-only; deploy of the merged PR is a no-op).
- Detaching/deleting the dead Blueprint object in the Render dashboard, if
  one still exists — CLI can't manage Blueprints; harmless either way.

## Tasks

- [x] **render.yaml rewrite.** Drop the entire `envVars:` block (all env
      claims). Keep the service shape (runtime, build/start commands,
      health check, rootDir, branch) and correct the stale facts:
      `plan: starter`, `region: oregon` (with a note about the Neon
      latency drift and the Phase 49 candidate). Header comment states the
      file is documentation only, the Blueprint sync is dead, and the
      dashboard is the source of truth. Keep an inventory of the
      dashboard-managed env-var keys (names only, no values) as comments
      so the file still answers "what does prod need set?".
- [x] **`render blueprints validate ./render.yaml`** still passes (the
      file remains a syntactically valid blueprint even though it is not
      connected).
- [x] **.env.example.** Fix the two comments claiming production values
      come "via render.yaml" (lines ~34, ~77) → the Render dashboard.
- [x] **deployment-overview.md.** Add a Phase 48 update note to the
      "Secrets live only in provider dashboards" shared decision: ALL env
      vars (not just secrets) are dashboard-managed now; render.yaml is
      documentation only.

## Verification

- [x] `/verify-stack` passes (no code touched — run anyway per workflow
      rule). *(2026-07-22: 425 passed; tsc 0 errors; lint 0 errors /
      22 warnings — same baseline as Phase 47. Note: the `/verify-stack`
      skill file itself was removed from `.claude/` in the repo cleanup
      merged with PR #41 — suite run manually per CLAUDE.md commands.)*
- [x] `render blueprints validate` output clean. *(2026-07-22: `{"valid": true}`, totalActions 0.)*
- [x] Live service untouched: `/api/health/` still 200 after merge; no new
      deploy config drift introduced (repo-only change; Render deploy of
      the merge is a code no-op). *(2026-07-22 post-merge: 3/3 requests
      200, 0.22-0.32 s.)*

## Related live verification done this session (Phase 47 leftover)

- `THROTTLE_DEMO_LOGIN=10/min` confirmed live: 30-request burst at
  `POST /api/auth/demo-login/` → exactly 20×200 (rate × 2 gunicorn
  workers, per-worker LocMemCache) then 10×429. Also re-confirms the
  PR #40 CF-Connecting-IP bucket keying for this scope.
