# Handoff: Phase 51 student onboarding — implemented, PR #48 open

## Current state

Phase 51 implementation is COMPLETE on branch `feat/phase-51-student-onboarding`
(6 commits off main after PR #47), pushed to `lms`, **PR #48 open**:
https://github.com/Cesar6060/LMS/pull/48 — NOT merged (user decision).

DOMAIN: user registered **stemquests.com** (2026-07-23, Cloudflare
Registrar, same account as the Worker). `frontend/wrangler.jsonc` now
declares it as a Custom Domain route — the merge deploy attaches DNS+TLS
automatically (validated with `wrangler deploy --dry-run`). README +
deployment-tools updated; cutover runbook rewritten with concrete values
(Part A app domain, Part B Resend email). Also: the live-site invite
failure the user hit is the OLD Gmail SMTP path (pre-phase-51 code) —
diagnosis confirmed no request ever reached local; the merge + Resend
swap replaces that path entirely.

- Backend: `CourseInvite` model + migration 0016 (additive, checker: SAFE);
  bulk invite create/list/revoke + public token detail/accept endpoints
  (courses/views.py, urls.py); old code-invite endpoint/helper/template
  removed; `clone_course_for_demo` command; `seed_demo_account` retargeted
  to DEMO101 (strips other enrollments every run); throttles: THROTTLE_USER
  default class + invite_send/invite_accept scopes (core/throttling.py adds
  ClientIPUserRateThrottle and a write-only scoped variant).
- Frontend: roster invite card + open-invites table (StudentRosterPage),
  `/invite/:token` AcceptInvitePage (create-account / auto-accept / dead-link
  screens), `/terms` + `/privacy` DRAFT pages, footer links on Login;
  services/invites.ts + types. All lazy-loaded.
- Ops: .github/workflows/db-backup.yml (daily pg_dump → R2, 14d/8w
  retention); runbooks phase-51-db-restore-steps.txt (restore DRILLED
  2026-07-23, counts matched prod) and phase-51-email-provider-steps.txt
  (Resend); .env.example + render.yaml inventory updated.

Verified: pytest **454 passed** (+29 new), tsc 0 errors, lint 0 warnings,
prod build clean. Migration 0016 applied to local Docker DB only.

## In progress / not done (all USER actions — spec lists them)

- Apply migration to Neon BEFORE merging: `DATABASE_URL=<neon> python
  manage.py migrate`, then merge PR #48.
- Post-merge on Neon: `clone_course_for_demo` then `seed_demo_account
  --reset` (demo moves to DEMO101; works against JAVA101 until then).
- Render env: THROTTLE_USER/THROTTLE_INVITE_SEND/THROTTLE_INVITE_ACCEPT.
- GitHub secrets for backups (NEON_DATABASE_URL, R2_ACCOUNT_ID,
  R2_BACKUPS_BUCKET, R2_BACKUPS_ACCESS_KEY_ID/SECRET) → one green run.
- Domain cutover env flips after merge: FRONTEND_URL=https://stemquests.com,
  add origin to CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS (keep
  workers.dev during transition); then Resend on stemquests.com (runbook
  Part B). Frontend Sentry DSN, ADMIN_URL flip (phase-50 runbook),
  UptimeRobot Gmail filter fix + repoint frontend monitor.
- Manual E2E (silence = passed): invite own email → accept → enrolled;
  revoke a second invite → revoked screen. Legal pages + DRAFT sign-off.

## Next steps

1. USER: migrate Neon → merge PR #48 → clone/seed commands → env vars.
2. USER: backup secrets, then dispatch db-backup workflow once (green run
   + object in R2 completes the backups checklist item).
3. Paste admin-curl outputs + live-check results into the phase 51 spec.

## Decisions made

- Invite API follows the app's mount convention: real paths are
  `/api/courses/courses/{code}/invites/` and `/api/courses/invites/{token}/`
  (spec shorthand said `/api/invites/`); frontend service hides it.
- Re-invite refreshes the existing non-revoked row (token+expiry, clears
  accepted_at); outcome `resent` only if it was still pending.
- Instructor's own email and DEMO_ACCOUNT_EMAIL are `invalid` invite targets.
- Demo instructor (instructor@demo.com) gets an unusable password.
- Attachments deliberately NOT cloned to DEMO101 (shared file storage;
  deleting an attachment deletes its file).

## Gotchas discovered

- Neon: verify restores via the DIRECT endpoint — the `-pooler` host can
  serve a stale connection that claims the DB is empty post-restore.
- `_clone` (pk=None trick) mutates in place — capture source pks first.
- DRF snapshots throttle rates at import: tests patch
  `ScopedRateThrottle.THROTTLE_RATES` / `UserRateThrottle.THROTTLE_RATES`.
- `gh`/git default to `origin` (archived repo) — use `lms` remote and
  `--repo Cesar6060/LMS`.

## Files to read first

- docs/specs/phase-51-student-onboarding.md — checklist + evidence section
- backend/courses/views.py (invite section, "Course Invites (Phase 51)")
- frontend/src/pages/auth/AcceptInvitePage.tsx
- docs/runbooks/phase-51-db-restore-steps.txt / -email-provider-steps.txt
