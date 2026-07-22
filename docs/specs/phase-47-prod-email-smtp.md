# Phase 47 — Production Email (Gmail SMTP)

## Goal

Make the email flows that already exist actually deliver in production.
Today `EMAIL_BACKEND` defaults to (and `render.yaml` hard-codes) the console
backend, so password-reset emails print to Render logs and never reach users —
called out since Phase 40 as "the biggest gap before real students." This
phase switches prod to Gmail SMTP (app password, sending from
cesarvillarreal11@gmail.com), fixes the password-reset email so its link
points at the frontend's `/reset-password?uid=…&token=…` route instead of
Django's default backend-relative `/reset/<uid>/<token>/` path, adds
defense-in-depth so the public demo account can never trigger outbound email,
throttles the anonymous reset endpoint, and locks all of it in with the
repo's first `mail.outbox` tests. Local dev keeps the console backend with
zero new setup.

## Out of scope

- Signup email verification changes — `ACCOUNT_EMAIL_VERIFICATION` stays
  `optional`; no allauth confirmation-template work.
- Custom domain / SPF / DKIM / dedicated provider (Resend, Brevo, SES) —
  revisit if STEM Quest gets its own domain.
- Celery or any real task queue — the `threading.Thread` best-effort sender
  in `core/email.py` stays as-is (announcement fan-out only).
- Grade-notification emails (PLAN.md references a template and an
  `assignments` app that don't exist — stale doc, not a task).
- Re-enabling public registration (`ALLOW_REGISTRATION` stays off in prod).
- Frontend feature work — the forgot/reset pages already exist and match the
  link format this phase adopts.

## Backend tasks

- [x] **Custom password-reset email.** Add `PasswordResetSerializer` override
      in `backend/accounts/serializers.py` and register it as
      `REST_AUTH['PASSWORD_RESET_SERIALIZER']` in
      `backend/config/settings.py`. Via `get_email_options()`, pass
      `extra_email_context={'frontend_url': settings.FRONTEND_URL}` and point
      at new templates so the emailed link is exactly
      `{FRONTEND_URL}/reset-password?uid=<uid>&token=<token>` (the format
      `frontend/src/pages/auth/ResetPasswordPage.tsx` parses from the query
      string).
- [x] **Reset email templates.** New
      `backend/templates/registration/password_reset_email.html` (branded,
      extending `templates/emails/base.html` like the existing invite /
      announcement templates) plus a plain-text body and a
      `password_reset_subject.txt`. No user-controlled HTML in the template.
- [x] **Demo outbound-email guard.** In `backend/core/email.py`
      `send_templated_email()`, refuse to send (log + return False) when the
      triggering user is the demo account (compare against
      `settings.DEMO_ACCOUNT_EMAIL`); thread a `triggered_by` user through
      the invite (`courses/views.py` `send_course_invite`) and announcement
      (`_notify_enrolled_students`) call sites. The demo user is a student
      and can't reach these instructor-only endpoints today — this is
      defense-in-depth in case a demo instructor is ever added.
- [x] **Throttle password reset.** Add a `password_reset` scoped throttle
      (env-gated like the existing `demo_login` scope in
      `settings.py:214-225`; e.g. `THROTTLE_PASSWORD_RESET`, unset locally,
      set in prod) applied to `/api/auth/password/reset/` — it's anonymous
      and now sends real email.
- [x] **`EMAIL_TIMEOUT`.** Add `EMAIL_TIMEOUT = config('EMAIL_TIMEOUT',
      default=10, cast=int)` to settings so a slow/blocked SMTP connection
      can't hang the synchronous reset/invite request threads.
- [x] **Tests (first `mail.outbox` coverage in the repo).**
      - Reset request → exactly one message in `mail.outbox`; body contains
        `{FRONTEND_URL}/reset-password?uid=` and a token; subject from the
        new subject template.
      - Full round trip: extract uid/token from the outbox body, POST them to
        `/api/auth/password/reset/confirm/`, then log in with the new
        password.
      - Reset request for an unknown email → 200 and empty outbox (no
        account enumeration).
      - Invite endpoint → message in outbox; announcement with
        `send_email=True` → messages only to students with
        `email_announcements=True`.
      - Demo guard: `send_templated_email` triggered by the demo user sends
        nothing.
      - Throttle scope engages when the env var is set (mirror the existing
        demo_login throttle test pattern if one exists).
- [x] **`render.yaml`.** Change `EMAIL_BACKEND` to
      `django.core.mail.backends.smtp.EmailBackend`; add literal
      `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`,
      `THROTTLE_PASSWORD_RESET`; add `EMAIL_HOST_USER`,
      `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` as `sync: false`
      (dashboard-set secrets, same pattern as `DEMO_ACCOUNT_PASSWORD`).
- [x] **Docs.** Update `docs/specs/deployment-overview.md` lines 19/54 (email
      is no longer console-only/out-of-scope); confirm `.env.example` Gmail
      block (lines 71-103) still matches reality.

## Frontend tasks

- [x] No code changes expected. Verify `ForgotPasswordPage.tsx` "check your
      email" copy and `ResetPasswordPage.tsx` query-param parsing against the
      new email link during the manual flow; fix copy only if it misleads
      (e.g. promises an email that comes from a personal Gmail address).
      *(Verified: ResetPasswordPage reads `uid`/`token` from the query string
      — matches the emailed link exactly; ForgotPasswordPage copy names no
      sender, so nothing misleads. No changes made.)*
- [x] `cd frontend && npx tsc --noEmit` still passes (no-op check since no
      changes planned).

## Rollout (operator runbook — written: `docs/runbooks/phase-47-email-rollout.txt`)

- [ ] USER: create a Google app password for cesarvillarreal11@gmail.com
      (requires 2-Step Verification on the Google account; Google Account →
      Security → App passwords). Never commit it; paste only into Render.
- [ ] USER: set `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (the app password),
      `DEFAULT_FROM_EMAIL=cesarvillarreal11@gmail.com`, and
      `THROTTLE_PASSWORD_RESET` (e.g. `5/hour`) in the Render dashboard.
- [ ] Merge PR → Render deploys → live verification below.

## Verification

- [x] `/verify-stack` passes (backend pytest incl. new email tests, tsc 0
      errors, lint no new warnings).
      *(Done 2026-07-22: 424 passed (9 new email tests), tsc 0 errors, lint
      0 errors / 22 warnings — same baseline as phase 46.)*
- [x] Local: `docker compose restart backend`, request a reset for a seeded
      user, confirm the console-backend output shows the branded body and a
      `{FRONTEND_URL}/reset-password?uid=…&token=…` link.
      *(Done 2026-07-22: reset for student1@demo.com printed subject "Reset
      your STEM Quest password", branded text+HTML body, and
      `http://localhost:5173/reset-password?uid=2&token=…`.)*
- [ ] Prod (after rollout): request a password reset for a real account you
      control on the live site → email arrives in the inbox from
      cesarvillarreal11@gmail.com; clicking the link opens
      `/reset-password` on
      https://stemquest.cesarvillarreal11.workers.dev with uid/token
      populated; completing the form changes the password; logging in with
      the new password works (then reset it back or use a throwaway
      account — do NOT use the demo account, its password is operator-managed).
- [ ] Prod: repeated anonymous reset requests hit the throttle (429) once
      past the configured rate.
- [ ] Prod: Render logs show no SMTP auth errors on deploy; a reset request
      no longer prints an email body to the logs.
