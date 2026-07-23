# Phase 51 — Student Onboarding: invites, legal pages, demo separation, ops hardening

## Goal

Take the platform from locked portfolio demo to professionally ready for real
students. Instructors invite students by email (multi-email paste); each invite
is a tokenized link that creates the student's account, marks the email
verified, enrolls them in the course, and logs them in — no open registration.
Real students may be minors whose parental consent is collected offline, so the
app needs a Privacy Policy and Terms of Service page (drafted plain-language,
marked DRAFT for user review — not legal advice) linked at account creation.
The public demo stays but moves to a cloned demo course (DEMO101, copied from
JAVA101) so visitors never share rosters, discussions, or leaderboards with
real students. Ops catches up to real-user stakes: automated Neon backups to
R2, transactional email on the user's own domain replacing personal Gmail,
frontend Sentry activated, rate limits for authenticated traffic, and the
phase-50 ADMIN_URL flip finally applied.

## Out of scope

- Open self-registration (`ALLOW_REGISTRATION` stays False; `/register` keeps
  redirecting to `/login`)
- In-app parental-consent flow (consent is handled offline by the user)
- CSV roster upload (multi-email paste only; CSV is a future phase if needed)
- Course catalog / browse-and-enroll UI (enrollment stays invite- or code-based)
- Payments, billing, seat limits
- Instructor self-service role assignment (stays Django-admin-only)
- Email delivery for notification types beyond invites/reset/announcements
  (new_lesson, reply, badge_earned stay in-app only)
- Grafana/OTel observability (Sentry + UptimeRobot remain the stack)
- Purpose-built demo content (DEMO101 is a clone of JAVA101, not new authoring)

## Backend tasks

### Invite system (courses app)

- [x] `CourseInvite` model: `course` FK, `email` (stored lowercased),
  `token` (unique, `secrets.token_urlsafe(32)`), `invited_by` FK(User),
  `created_at`, `expires_at` (default now + 14 days), `accepted_at` (null),
  `revoked_at` (null). Property/queryset helpers: `is_pending`, `is_expired`.
  Constraint: at most one non-revoked invite per (course, email) — re-inviting
  the same email refreshes token + expiry on the existing row instead of
  duplicating. Migration.
- [x] `POST /api/courses/{code}/invites/` — permission `IsCourseInstructor`.
  Body `{"emails": ["a@x.com", ...]}` (frontend parses the paste into a list;
  backend re-validates each with Django's email validator, lowercases, dedupes).
  Per-email outcomes returned in the response: `invited`, `resent`
  (pending invite existed — token/expiry refreshed, email re-sent),
  `already_enrolled` (active enrollment exists — skipped), `invalid`.
  Sends invite emails via `send_emails_async` (existing `core/email.py`
  helper) — template `emails/course_invite_link.html`, link
  `{FRONTEND_URL}/invite/{token}`, includes course title + inviter name.
- [x] `GET /api/courses/{code}/invites/` — `IsCourseInstructor`. Lists invites
  with email, status (pending/accepted/expired/revoked), created/expires dates.
- [x] `DELETE /api/courses/{code}/invites/{invite_id}/` — `IsCourseInstructor`.
  Sets `revoked_at` (soft revoke; accepted invites cannot be revoked → 400).
- [x] `GET /api/invites/{token}/` — `AllowAny`. Returns
  `{course_title, email_masked, status, account_exists}` for the accept page.
  Invalid/expired/revoked/accepted tokens return their status, never 500.
  `account_exists` = a User with that email already exists.
- [x] `POST /api/invites/{token}/accept/` — `AllowAny`, scoped anon throttle
  `invite_accept` (env `THROTTLE_INVITE_ACCEPT`, prod ~10/hour).
  Two paths, both atomic:
  - No existing account: body `{first_name, last_name, password, agree_terms}`.
    Validates password with Django validators, requires `agree_terms=true`,
    creates the user (`is_instructor=False`), marks allauth EmailAddress
    verified (they proved the address by clicking), creates/reactivates the
    Enrollment, sets `accepted_at`, returns a JWT pair (same shape as
    demo-login) so the frontend logs them straight in.
  - Existing account: request must be authenticated as the invited email
    (else 403 with `account_exists: true` so the frontend routes to login).
    Enrolls/reactivates, sets `accepted_at`, returns the enrollment.
- [x] Demo account guard: invites addressed to `DEMO_ACCOUNT_EMAIL` are
  rejected as `invalid` (mirrors the reset/change exclusions).
- [x] Deprecate the old code-only invite: `send_course_invite`
  (`courses/views.py:1531`) and its URL are removed; the enrollment-code
  self-enroll endpoints stay untouched as the secondary path.
- [x] Tests (pytest): bulk create with mixed outcomes (new/resent/enrolled/
  invalid/demo-email); permission denied for student and non-owner instructor;
  accept happy path creates verified user + enrollment + JWT; accept for
  existing account (authed = enrolls, anon = 403 account_exists); expired,
  revoked, reused tokens rejected; re-invite refreshes rather than duplicates;
  accept is atomic (no user row left behind on enrollment failure).

### Demo separation

- [x] Management command `clone_course_for_demo`: deep-copies JAVA101 →
  `DEMO101` ("Java Fundamentals — Demo"), owner `instructor@demo.com`
  (created if missing), copying units → lessons → sections → quizzes/questions.
  Idempotent: re-running refreshes content, preserves the DEMO101
  `enrollment_code`. Refuses to run if JAVA101 doesn't exist.
- [x] `seed_demo_account` updated: demo user's enrollment + baseline progress
  target DEMO101 (removed from JAVA101 if previously enrolled); the periodic
  wipe (`_wipe_visitor_data`) scoped to DEMO101.
- [x] Tests: clone idempotency (counts stable across two runs), demo account
  ends up enrolled only in DEMO101.

### Throttling (settings + core/throttling.py)

- [x] Add a user-rate throttle class (keyed on user id) to
  `DEFAULT_THROTTLE_CLASSES`; rate from env `THROTTLE_USER`
  (default `None` = off, prod ~120/min) — same pattern as `THROTTLE_ANON`.
- [x] Scoped throttle on invite send (`THROTTLE_INVITE_SEND`, prod ~30/hour)
  and invite accept (above).
- [x] Tests: user throttle honors env-off default; scoped rates enforced.

## Frontend tasks

- [x] Types: `CourseInvite`, invite-batch result, accept payloads
  (`types/`); service `services/invites.ts` (create batch, list, revoke,
  get by token, accept).
- [x] `StudentRosterPage`: new "Invite students" card — textarea accepting
  comma/newline-separated emails, submit, then a per-email results summary
  (sent / re-sent / already enrolled / invalid). Below it, a pending-invites
  table (email, status, expires) with per-row Resend and Revoke buttons.
  Replaces the old single-email code-invite UI. Follow UI prefs: large type,
  real buttons, wide layout.
- [x] `AcceptInvitePage` at public route `/invite/:token` (lazy-loaded like
  all pages). Loads `GET /api/invites/{token}/`:
  - pending + no account → form: first name, last name, password (+ confirm),
    required checkbox "I agree to the Terms of Service and Privacy Policy"
    (links open in new tab). Submit → tokens stored via AuthContext →
    redirect to the course page.
  - pending + account exists → "This invite is for {email_masked}. Log in to
    join the course." → login (preserving the invite token) → auto-accept →
    course page.
  - expired/revoked/accepted/invalid → clear, friendly status screen with a
    link to `/login`.
- [x] Legal pages: `/terms` and `/privacy` public routes rendering drafted
  plain-language content (tailored to actual data collected: name, email,
  course progress, grades; minors with offline parental consent; Sentry with
  PII scrubbed; no ads/tracking). Both pages carry a visible "DRAFT — pending
  review" banner until the user signs off. Footer links added on Login and
  AcceptInvite pages.
- [x] `tsc --noEmit` 0 errors, `npm run lint` stays at 0 warnings, prod build
  clean (lazy chunks for the new pages).

## Ops / infra tasks (mix of code and USER actions)

- [ ] Backups: GitHub Actions workflow (daily cron) running `pg_dump` against
  Neon, uploading compressed dumps to a private R2 backups bucket; prunes to
  14 daily + 8 weekly. Secrets: `NEON_DATABASE_URL`, R2 keys. Workflow
  committed; USER adds the repo secrets. Restore runbook written as
  `docs/runbooks/phase-51-db-restore-steps.txt` (plain text) and drilled once
  against a scratch Neon branch (evidence in spec).
- [ ] Email provider swap (code side is env-only): `.env.example` +
  `render.yaml` env inventory updated for the transactional provider
  (e.g. Resend SMTP) on the user's own domain; runbook
  `docs/runbooks/phase-51-email-provider-steps.txt` covering DNS records
  (SPF/DKIM), provider setup, Render env flip, and a send test. USER executes;
  verification is a received invite email from the new domain.
- [ ] Frontend Sentry activation: USER adds `VITE_SENTRY_DSN` (+
  `SENTRY_AUTH_TOKEN` if sourcemaps) to the Cloudflare Pages build per
  phase-40 notes; verified by a forced test error appearing in Sentry.
- [ ] ADMIN_URL flip (phase-50 carryover): USER applies
  `docs/runbooks/phase-50-admin-url-steps.txt`; verify `/<slug>-console/`
  serves admin login and `/admin/` 404s (curl output pasted here).
- [ ] UptimeRobot alert deliverability: USER checks the Gmail filter that sent
  phase-40 alert emails to Trash; fix noted here.

## Verification

- [ ] `/verify-stack` green: full pytest suite (425 existing + new invite/
  demo/throttle tests), `tsc --noEmit` 0 errors, lint 0 warnings.
- [x] Backend flow (pytest, exact cases listed per section above) — invite
  lifecycle: create → accept → enrolled → token dead on reuse.
- [ ] Manual end-to-end (USER, silence = passed): from the roster page, invite
  a personal email → email arrives from the new domain → accept link → create
  account with ToS checkbox → land enrolled in the course → appears on the
  roster; revoke a second pending invite and confirm its link shows the
  revoked screen.
- [ ] Demo check: "Try the demo" on the live site lands in DEMO101; JAVA101
  roster contains no demo account; demo visitor actions never appear to a
  JAVA101 student.
- [ ] `/terms` and `/privacy` render on the live site; links present on Login
  and AcceptInvite.
- [ ] Backups: one green scheduled workflow run; dump object visible in R2;
  restore drill output recorded.
- [ ] Admin: `curl -o /dev/null -w '%{http_code}' https://stemquest-api-va.onrender.com/admin/`
  → 404, and the slug path → 200/302 (paste outputs).
- [ ] Sentry: forced frontend error visible in the Sentry project.

## Implementation notes & evidence (2026-07-23)

- **API paths**: the courses app mounts at `/api/courses/`, so the real
  endpoints follow the app's existing convention:
  `/api/courses/courses/{code}/invites/` (POST/GET),
  `/api/courses/courses/{code}/invites/{id}/` (DELETE),
  `/api/courses/invites/{token}/` (GET) and
  `/api/courses/invites/{token}/accept/` (POST). The frontend service hides
  this; the emailed link is unchanged: `{FRONTEND_URL}/invite/{token}`.
- **Old invite retired**: `send_course_invite`, its URL, the
  `send_course_invitation_email` helper, and `emails/course_invitation.html`
  are all removed; enrollment-code self-enroll is untouched.
- **Migration**: `courses/0016_courseinvite_and_more.py` (new table +
  partial unique constraint; no changes to existing tables).
- **Restore drill (done 2026-07-23)**: `pg_dump -Fc` of production Neon
  (project shy-cloud-68280619) → scratch branch `phase51-restore-drill`
  (br-lucky-lab-av8f490s, auto-expires 2026-07-24T12:00Z) → fresh
  `restore_drill` database → `pg_restore` → sanity counts
  users=3 / courses=1 / enrollments=1 / lessons=20, exactly matching
  production. Gotcha recorded in the runbook: verify through the DIRECT
  endpoint, not the `-pooler` one (stale pooled connections can report an
  empty DB right after restore).
- **Deploy sequence for demo separation** (after merge, one-time, from a
  dev machine with DATABASE_URL pointed at Neon):
  1. `python manage.py migrate`
  2. `python manage.py clone_course_for_demo`
  3. `python manage.py seed_demo_account --reset`
  Until step 3 runs, the demo account stays enrolled in JAVA101 and
  demo-login keeps working against it.
- **New prod env vars (Render dashboard)**: `THROTTLE_USER=120/min`,
  `THROTTLE_INVITE_SEND=30/hour`, `THROTTLE_INVITE_ACCEPT=10/hour`.
- **GitHub repo secrets for backups**: `NEON_DATABASE_URL`,
  `R2_ACCOUNT_ID`, `R2_BACKUPS_BUCKET`, `R2_BACKUPS_ACCESS_KEY_ID`,
  `R2_BACKUPS_SECRET_ACCESS_KEY` (create a dedicated private bucket +
  bucket-scoped R2 API token first).
- **Domain (2026-07-23)**: user registered **stemquests.com** (Cloudflare
  Registrar, same account). `frontend/wrangler.jsonc` now declares it as a
  Custom Domain route, so the merge deploy attaches DNS + TLS
  automatically. Remaining USER env flips (FRONTEND_URL, CORS, CSRF, then
  Resend SMTP): docs/runbooks/phase-51-email-provider-steps.txt.
