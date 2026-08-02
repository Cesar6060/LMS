# Handoff: Phase 49 — Virginia service live, cutover in flight

## Current state

Phase 49 steps A+B COMPLETE, C in flight. New service stemquest-api-va
(srv-d9go1em1a83c73f50r2g, Virginia, Starter) is live at
https://stemquest-api-va.onrender.com — Render granted the clean name
(no random suffix; that only happens on collisions). Verified: shallow
+deep health 200 with deep ≈ shallow (~0.12-0.19 s; Oregon's +70-130 ms
DB penalty gone), demo-login JWTs, 30-burst → 20×200/10×429, admin 302,
SMTP reset request 200 with clean logs. All 28 env vars set (19 by
agent via browser, 9 secrets by user; DEMO_ACCOUNT_PASSWORD and
ADMIN_URL intentionally omitted — service doesn't need them, old
service never had them; prod admin is at default /admin/).
Merged: PR #43 (phase 48/49 docs), PR #44 (dual-origin CSP + README).
Cloudflare VITE_API_URL flipped to https://stemquest-api-va.onrender.com/api
(build var, stemquest worker). Verified this session: pytest 425, tsc 0,
lint 0/22. Also: .claude/ skills/agents/rules restored from git history
(96dba56 deleted them; .claude/ is now gitignored = local-only).

## In progress / not done

- Frontend rebuild with the new VITE_API_URL: triggered by THIS commit
  landing on main (no retry-build button in the Workers UI; env-var edit
  alone doesn't rebuild). ALLOWED_HOSTS on the new service is the
  .onrender.com placeholder — tighten to stemquest-api-va.onrender.com
  during D4 cleanup.
- C3 click-through + C4 UptimeRobot repoint (803564203 shallow,
  803564235 deep keyword) — agent does these right after this push.
- D: suspend old Oregon service after C verifies; ~3-day window; delete;
  cleanup PR (drop old origin from CSP, render.yaml region/id, tighten
  ALLOWED_HOSTS, check remaining spec boxes).

## Next steps

1. Confirm frontend build picked up the new URL (bundle references
   stemquest-api-va), click through live site with console open.
2. Repoint both UptimeRobot monitors to the new URL; confirm UP.
3. Suspend old service (dashboard); watch the 3-day window.
4. D3+D4: delete old service, cleanup PR, close the phase 49 spec.

## Decisions made

- Rebuild-by-push instead of hunting a retry button: docs commit to main
  is allowed post-verify and triggers both deploys (backend one is a
  code no-op).
- Kept old API origin in CSP until D4 so rollback stays a pure
  VITE_API_URL flip (runbook ROLLBACK section still valid).

## Gotchas discovered

- Render "New Web Service" UI: react inputs ignore synthetic typing —
  use form_input by ref; an empty env row blocks submit ("Required").
- Cloudflare Workers Builds: editing a build var does NOT rebuild, and
  version-history "..." menu has no retry — only a new push builds.
- The stale-branch race: PR #42 was merged BEFORE the phase 49 docs were
  pushed to its branch — always check PR state before pushing more
  commits to an open PR's branch (recovered via PR #43).

## Files to read first

- docs/specs/phase-49-region-move-virginia.md — spec with evidence notes
- docs/runbooks/phase-49-region-move-steps.txt — remaining steps C3-D4
- docs/handoffs/2026-07-22-phase-48-retire-render-yaml.md — prior session
