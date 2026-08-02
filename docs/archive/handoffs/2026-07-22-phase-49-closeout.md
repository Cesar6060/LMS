# Handoff: Phase 49 FULLY closed — API in Virginia, old service deleted

## Current state

Phase 49 COMPLETE except one deferred box. The API now runs in Virginia:
stemquest-api-va (srv-d9go1em1a83c73f50r2g), Starter, auto-deploy from
main, https://stemquest-api-va.onrender.com. Deep health ≈ shallow
(~0.12-0.19 s; Oregon cost +70-130 ms per DB query). Cutover done:
VITE_API_URL flipped (Cloudflare build var), frontend rebuilt, live
click-through clean (zero console errors, all API calls to -va),
UptimeRobot 803564203 + 803564235 repointed and UP. Old Oregon service
stemquest-api SUSPENDED by user 2026-07-22 (suspended = not billed).
Closeout PR (this branch): render.yaml identity → new service, spec
checked with evidence. Verified this session: pytest 425, tsc 0 errors,
lint 0 errors / 22 warnings. No migrations in this phase.

## In progress / not done

- Nothing in-flight. All spec boxes checked; phase 49 is closed.
- Silent tail checks (USER, silence = passed): open one instructor page
  with an uploaded image (first R2 exercise on the new service); note if
  the 07-22 reset email reached the inbox.

## Next steps

1. Merge the final cleanup PR if not yet merged (CSP old-origin removal,
   render.yaml header, spec close) — deploys are no-ops.
2. /start-phase 50 is now the right next command. Candidates noted along
   the way: PLAN.md is badly stale vs phases 41-49 (retire or refresh);
   ADMIN_URL still on default /admin/ (phase 43 intent, never applied).
3. IMPORTANT context for future infra work: the LMS Blueprint
   (exs-d9fdhi6rnols73bo0rg0) RE-ADOPTED stemquest-api-va when
   render.yaml's name matched (discovered at phase 49 close). Service-
   shape fields in render.yaml now APPLY on push to main; env vars remain
   dashboard-only (no envVars block — keep it that way). plan:/region:
   edits in render.yaml are live changes now.

## Decisions made

- User waived the 3-day window and deleted the old service same-day;
  ALLOWED_HOSTS tightened to the exact host (redeploy verified).
- render.yaml header rewritten AGAIN at close: shape-sync is live (see
  next steps #3), env vars stay dashboard-only — the file must neither
  overclaim (phase 41-48 bug) nor underclaim (post-adoption reality).

## Gotchas discovered

- Suspended Render services are not billed — "delete to stop paying" is
  a false economy vs the rollback value of suspend.
- Demo account cannot exercise R2 (no media objects reachable) — future
  media verification needs an instructor/admin login.
- UptimeRobot update-monitor API works fine for URL repoints (no
  dashboard needed); monitor IDs in the phase 49 spec.

## Files to read first

- docs/specs/phase-49-region-move-virginia.md — spec, one open box
- docs/runbooks/phase-49-region-move-steps.txt — D3/D4 steps + rollback
- render.yaml — updated service identity (documentation-only file)
