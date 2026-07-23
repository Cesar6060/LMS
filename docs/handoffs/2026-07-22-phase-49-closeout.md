# Handoff: Phase 49 closed — API live in Virginia; delete old service ~07-25

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

- ONE spec box open (docs/specs/phase-49-region-move-virginia.md:118):
  delete the old service after a clean window, ~2026-07-25.
- R2 presigned URLs never exercised on the new service — demo account
  reaches no uploaded media (YouTube embeds, null avatar). USER opens
  any instructor page with an uploaded image once; silence convention.
- Reset-email inbox arrival not explicitly confirmed (request 200, logs
  clean); silence convention.

## Next steps

1. ~2026-07-25, if monitors stayed green: USER deletes old service
   stemquest-api (srv-d9fdm3jh523c73f0rlkg) in the Render dashboard;
   confirm billing shows a single Starter instance.
2. Then a small cleanup PR: remove https://stemquest-api.onrender.com
   from frontend/public/_headers connect-src; tighten new service's
   ALLOWED_HOSTS env var from `.onrender.com` to
   stemquest-api-va.onrender.com (dashboard edit → auto redeploy);
   check the last spec box.
3. Optional hardening backlog: set ADMIN_URL off default /admin/ (never
   actually applied — phase 43 intent lost to the dead Blueprint sync).

## Decisions made

- Suspend-then-delete instead of immediate delete: suspension already
  stops billing, keeps instant-resume rollback while R2/email tail
  checks ride the window.
- Old CSP origin stays until the old service is deleted (rollback =
  pure VITE_API_URL flip; runbook ROLLBACK section valid until D3).
- Phase closed with D3 explicitly deferred rather than held open.

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
