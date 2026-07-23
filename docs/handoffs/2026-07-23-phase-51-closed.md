# Handoff: Phase 51 CLOSED — live, verified, first real signup done

## Current state

Phase 51 is DONE and in production. main = e1fb3b7 (PR #54). Close-out
verify on main: pytest 454 passed, tsc 0 errors, lint 0 warnings.

Merged today: #48 feature (user-merged) · #49 cutover evidence +
recovered commits · #50 wrangler workers_dev pin (outage fix) · #51
close-out docs · #52 Resend verified · #53 stale-chunk self-heal ·
#54 E2E/Sentry evidence.

Live and agent-verified: https://stemquests.com (custom domain;
workers.dev kept during transition, deploys idempotent for both);
invites end-to-end (Resend email from noreply@stemquests.com → accept →
account #5 created, verified, enrolled — first REAL student signup
2026-07-23); DEMO101 demo separation; throttles (user 120/min,
invite_send 30/hour, invite_accept 10/hour); daily Neon→R2 backups
(green run, dump in R2, restore drilled); Sentry both halves (frontend
proved by catching a real bug); UptimeRobot incl. stemquests.com.

## In progress / not done (USER — explicitly deferred "housekeeping")

- Revoke old Gmail app password (dead since Resend; Sentry showed
  SMTPAuthenticationError was yesterday's invite failure).
- ADMIN_URL flip (phase-50 runbook; user generates slug) + paste curls
  into phase-51 spec (last unchecked box).
- UptimeRobot Gmail filter fix (alerts going to Trash).
- Legal DRAFT sign-off → then remove banners on /terms + /privacy.
- Optional: revoke a pending invite, confirm revoked screen.

## Next steps

1. Housekeeping above, whenever — none of it blocks students.
2. Next phase is a fresh planning session (no roadmap file; specs +
   handoffs are the source of truth).
3. Sentry backlog worth a look next phase: N+1 query on
   /api/courses/{code}/quizzes/ (STEMQUEST-DJANGO-5, low).

## Decisions made

- Deploy-stale tabs self-heal via vite:preloadError reload (30s guard)
  instead of pinning old assets — one-liner, fixes the class of bug.
- workers.dev stays enabled (wrangler pins workers_dev/preview_urls
  true); drop later by flipping those to false.

## Gotchas discovered

- wrangler + routes w/o workers_dev:true disables workers.dev on EVERY
  deploy (caused today's outage; comment lives in wrangler.jsonc).
- Deploys rotate all lazy-chunk hashes → open tabs crash on navigation
  (fixed, PR #53). Merge-before-migrate caused ~35 min of roster 500s —
  migrate Neon BEFORE merging backend schema changes.
- Sentry issue feed (cesar-villarreal.sentry.io) is the fastest
  prod-debugging tool this stack has — check it first.

## Files to read first

- docs/specs/phase-51-student-onboarding.md — full evidence trail
- docs/handoffs/2026-07-23-phase-51-cutover-and-outage.md — cutover day
- frontend/src/main.tsx (preloadError) + frontend/wrangler.jsonc
