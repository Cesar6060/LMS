# Handoff: Phase 48 — retire render.yaml as prod config source

## Current state

Phase 48 is code-complete on PR #42 (chore/phase-48-retire-render-yaml,
CI green, AWAITING MERGE — merge was permission-blocked for the agent).
Direction was user-confirmed this session: retire render.yaml rather than
reconnect the Blueprint (a sync of the stale file would have re-applied
`plan: free` and re-broken SMTP).

Changes on the PR:
- render.yaml: envVars block gone; documentation-only header; corrected
  facts (plan: starter, region: oregon); names-only inventory of
  dashboard-managed vars. Still a valid blueprint (`render blueprints
  validate`: valid, totalActions 0).
- .env.example: two "via render.yaml" comments now point at the dashboard.
- deployment-overview.md: Phase 48 note — ALL Render env vars are
  dashboard-managed, render.yaml is documentation only.
- New spec docs/specs/phase-48-retire-render-yaml.md (all boxes checked
  except the post-merge health check).

Also done this session (phase 47 leftovers):
- Docs close-out PR #41 confirmed merged; local main synced; branch deleted.
- THROTTLE_DEMO_LOGIN verified live: 30-burst at POST /api/auth/demo-login/
  → exactly 20×200 (10/min × 2 workers, per-worker LocMemCache) then
  10×429. Handoff's startCommand confirmation also done (dashboard matches
  render.yaml exactly, --workers 2 --timeout 120).

Verified: pytest 425 passed (in docker), tsc 0 errors, lint 0 errors /
22 warnings (baseline). CI green on PR #42.

## In progress / not done

- MERGE PR #42 (repo-only; the Render deploy it triggers is a code no-op).
- After merge: check the last spec box — `/api/health/` still 200.

## Next steps

1. Merge PR #42, confirm /api/health/ returns 200, check the final spec box.
2. PHASE 49 — region move Oregon → Virginia is now FULLY PLANNED (same
   session, user-requested): spec at
   docs/specs/phase-49-region-move-virginia.md, operator runbook at
   docs/runbooks/phase-49-region-move-steps.txt (both on PR #42).
   Execution starts at runbook step A (gather secrets) whenever the user
   is ready — steps A-B are zero-risk (old service keeps serving).
   Planning facts pinned this session:
   - New Render services get a random-suffixed URL (observed on another
     service in this workspace), so the clean stemquest-api.onrender.com
     is NOT reclaimable — the plan treats the URL change as given.
   - Complete API-URL consumer list is in the spec; the non-obvious one
     is frontend/public/_headers CSP connect-src (frontend cannot call
     the new API until its origin is added — sequenced as cutover C1,
     keeping the old origin for pure-config rollback).
   - Fresh SECRET_KEY on the new service (old is vault-locked) → SIMPLE_JWT
     sessions and in-flight reset links die at cutover. Accepted.
   - UptimeRobot monitors to repoint: 803564203 (shallow), 803564235
     (deep keyword).

## Decisions made

- Retire render.yaml (user-confirmed via question) — dashboard is the
  single source of truth for ALL Render env vars, not just secrets.
- Region drift recorded as phase 49 candidate, not bundled into 48.

## Gotchas discovered

- The `.claude/` skills (verify-stack, handoff, start-phase), rules, and
  agents files were DELETED from the repo in the cleanup merged via PR #41
  — but CLAUDE.md still tells sessions to run /verify-stack and /handoff.
  Run the suite manually (docker compose exec backend pytest; frontend
  tsc + lint) and write handoffs by hand until CLAUDE.md is updated or the
  skills are restored.
- No local venv: backend pytest must run inside the docker container
  (`docker compose exec -T backend pytest`), not on the host.
- render CLI v2.21 cannot list/manage Blueprints (`blueprints validate`
  only) and env-var reads are permission-blocked; `services list -o json`
  works and is how the plan/region drift was found.
- gh CLI defaults to the old `origin` (dev-learning-platform) — always
  pass `--repo Cesar6060/LMS` or fetch/push via the `lms` remote.

## Files to read first

- docs/specs/phase-48-retire-render-yaml.md — spec, findings, rationale
- render.yaml — the rewritten documentation-only file
- docs/handoffs/2026-07-22-phase-47-closeout-throttle-hotfix.md — prior
