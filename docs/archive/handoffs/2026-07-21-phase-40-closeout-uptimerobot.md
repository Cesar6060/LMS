# Handoff: Phase 40 CLOSED — UptimeRobot live, backend smoke test done

## Current state

Phase 40 (observability) is **fully closed** this session. Every spec
item is ticked, waived, or explicitly moved to backlog. The close-out
PR (branch `docs/phase-40-close`) carries docs + workflow files only —
zero code changes since PR #29.

What changed since the previous phase-40 handoff:

- **UptimeRobot: UN-DESCOPED and LIVE.** Cesar created the account and
  three monitors in the dashboard, then connected the UptimeRobot MCP
  server. The deep-DB keyword monitor was created inverted
  (ALERT_EXISTS instead of ALERT_NOT_EXISTS) and alarmed against a
  healthy endpoint; the MCP API can't flip keywordType on update, so
  it was recreated correctly (id 803564235). All three monitors UP:
  - Shallow health `/api/health/` every 5 min (id 803564203) —
    keep-warm + uptime, never touches the DB
  - Deep DB keyword `/api/health/?deep=1` every 60 min (id 803564235)
    — alerts when `"database": "ok"` is missing
  - Frontend `stemquest.cesarvillarreal11.workers.dev` every 5 min
    (id 803564204)
- **Alert-email delivery PROVEN** — the inverted monitor's false alarm
  sent a real DOWN email that reached Gmail; no scratch monitor needed.
- **Backend Sentry smoke test (step 6) DONE**: 500 triggered, event
  confirmed in stemquest-django, `SENTRY_DEBUG_ENDPOINT` removed from
  Render, endpoint re-verified 404, `/api/health/` 200.
- **Frontend Sentry smoke test (step 7) WAIVED** by Cesar at close
  ("let's be done"). Frontend Sentry is live and source maps verified
  indirectly; if frontend stack traces ever look unreadable, the
  one-minute console test is written into the spec.

## Verification evidence (2026-07-21, this session)

- `/verify-stack` PASS: pytest **376 passed** (in Docker), tsc 0
  errors, lint 0 errors / 22 warnings (baseline).
- `curl /api/sentry-debug/` → 404, `curl /api/health/` → 200.
- All three UptimeRobot monitors report UP via MCP.

## LOOSE ENDS from this session (small, do in dashboards)

1. **Delete the paused monitor** named "DELETE ME — inverted keyword
   (replaced by 803564235)" (id 803564196) in the UptimeRobot
   dashboard — the MCP server has no delete tool.
2. **Gmail Trash mystery**: all three UptimeRobot emails landed in
   Trash, unread. If Cesar didn't trash them manually, a Gmail filter
   is eating alerts — check Settings → Filters. An unseen alert is no
   alert.

## NEXT SESSION: portfolio polish (unchanged priorities)

1. **Update the README** — present the project for portfolio viewers
   (what it is, the live URL, the stack, screenshots). Source
   material: `docs/deployment-tools.txt`.
2. **Demo account** `jdoe@demo.com` / `Admin123!` — plain student or
   instructor, NEVER superuser (credentials will be public); enroll in
   JAVA101 with some progress; consider periodic reset since anything
   it writes is world-editable.

## Also still open (older backlog, in impact order)

1. **Email doesn't send in prod** — `EMAIL_BACKEND` defaults to
   console; password-reset emails go to Render logs. Biggest gap
   before real students.
2. **DB backups** — occasional `pg_dump` against Neon.
3. Delete `r2-check@example.com` via `/admin/` (Phase 39 leftover;
   moved out of the phase-40 spec as non-gating).
4. Bundle code-splitting (1.29 MB warning).
5. Local dev: stale pre-recharts `node_modules` volume (Phase 38).

## Gotchas

- **UptimeRobot MCP limits**: no delete-monitor tool; update-monitor
  cannot change keywordType (recreate instead). `.mcp.json` (now
  committed) carries the server config; `/mcp` to re-authenticate.
- Keyword monitors: match against the EXACT response body. DRF renders
  compact JSON in some configs — ours serves `"database": "ok"` with a
  space, which is what the monitor expects.
- rollup darwin-arm64: any host `npm install` drops the mac binary —
  fix is `npm install --no-save @rollup/rollup-darwin-arm64`.
- `frontend/tsconfig.tsbuildinfo` churns — keep it out of commits.
- PLAN.md's phase table ends at Phase 33; phases 34+ live entirely in
  `docs/specs/` + `docs/handoffs/`.

## Files to read first

- `docs/specs/phase-40-observability.md` — final checklist state
- `docs/runbooks/phase-40-observability-steps.txt` — AS-RUN history
  including the inverted-monitor incident
- `PHASE-WORKFLOW.txt` / `.claude/skills/finish-phase/` — the phase
  workflow tooling committed with this close-out
