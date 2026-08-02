# Handoff: Phase 51 cutover executed + workers.dev outage fixed

## Current state

Phase 51 is LIVE in production. PRs #48 (feature), #49 (cutover evidence
+ recovered commits), #50 (wrangler fix) all merged. Close-out verify:
pytest 454 passed, tsc 0 errors, lint 0 warnings.

Production (all agent-verified):
- https://stemquests.com serves the app (Worker custom domain); the old
  workers.dev URL also serves (transition). /terms /privacy /invite/:token
  all 200.
- Neon migrated (0016); DEMO101 cloned on prod; demo account enrolled
  ONLY in DEMO101 (live demo-login shows just DEMO101).
- Render env: FRONTEND_URL=https://stemquests.com; CORS/CSRF carry both
  origins (verified via preflight); THROTTLE_USER=120/min,
  THROTTLE_INVITE_SEND=30/hour, THROTTLE_INVITE_ACCEPT=10/hour.
- Backups LIVE: bucket stemquest-db-backups (private) + scoped token;
  5 repo secrets; green run; daily/stemquest-2026-07-23.dump (232 KB) in
  R2. Daily cron 08:17 UTC.
- UptimeRobot: stemquests.com monitor (user-created) UP; workers.dev +
  API monitors unchanged.

INCIDENT (resolved): PR #49's deploy disabled the workers.dev subdomain
— wrangler does this whenever a `routes` block lacks `workers_dev: true`
— taking both URLs down with "error code: 1042". Version rollback did
NOT help (domain config, not code). Fix: dashboard toggles re-enabled,
then PR #50 pinned workers_dev+preview_urls true. Post-fix deploy left
both URLs at 200.

## In progress / not done (USER)

- **Resend signup** — THE blocker: EMAIL_* still points at broken Gmail,
  so invite/reset emails DO NOT SEND. Then runbook Part B (agent can
  drive DNS + env once the account exists).
- Manual E2E invite test (blocked on Resend) + legal DRAFT sign-off.
- Sentry: build vars (VITE_SENTRY_DSN etc.) already exist in Workers
  Builds settings — likely only the forced-test-error check remains.
- ADMIN_URL flip (user generates slug; phase-50 runbook); UptimeRobot
  Gmail filter fix.

## Next steps

1. USER: resend.com signup → tell agent → DNS records, env flip, test
   invite (closes email + manual E2E items).
2. Remaining spec boxes: admin curl outputs, Sentry test error.
3. Next phase planning is otherwise unblocked.

## Decisions made

- workers.dev stays enabled alongside stemquests.com during transition
  (wrangler config now pins it; drop later by flipping workers_dev).
- Render env edited via browser: reveal-value-first, then retype —
  form_input by ref on masked rows hit the wrong row once; that edit
  session was cancelled unsaved and redone.

## Gotchas discovered

- wrangler + `routes` w/o `workers_dev: true` DISABLES workers.dev on
  every deploy (the outage). Comment now lives in wrangler.jsonc.
- Workers version rollback does not revert domain/subdomain config.
- Merging a PR does not include commits pushed after merge — 3 commits
  stranded on the phase-51 branch were recovered via PR #49.
- Local DNS negative-caches brand-new domains; verify with dig @1.1.1.1
  / curl --resolve.

## Files to read first

- docs/specs/phase-51-student-onboarding.md — cutover log + incident
- frontend/wrangler.jsonc — the workers_dev pin + outage comment
- docs/runbooks/phase-51-email-provider-steps.txt — Part B is next
