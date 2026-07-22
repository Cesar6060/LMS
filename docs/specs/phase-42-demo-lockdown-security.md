# Phase 42: Demo Lockdown + Security Hardening

## Goal

Turn the live site into a safe **public demo** and close the security
holes that matter once anyone can log in as the shared demo student.
Two threads: (1) lock the app to a single demo login — no self-registration,
JAVA101 as the sandbox course; (2) fix the exploitable issues a malicious
visitor could reach with the published demo credentials, plus the config
hardening a public deployment needs.

Follow-on to Phase 41 (PR #32, merged), which created the `jdoe@demo.com`
demo account and portfolio README.

## Context / threat model

- The demo password (`Admin123!`) is published in the README, so treat
  every visitor as an attacker holding valid demo credentials.
- Two independent audits (config + application-layer) were run; findings
  drove this phase. The critical one — self-promotion to instructor — was
  a real, one-request break of the authz model.

## Deliverables

### Demo lockdown
- [x] Public self-registration gated behind `ALLOW_REGISTRATION` (default
      **off**). When off, `POST /api/auth/registration/` returns 403 and the
      real allauth registration urls are never mounted — bypass-proof at the
      API, not just a hidden button.
- [x] Frontend: `/register` route removed (redirects to `/login`),
      `RegisterPage.tsx` deleted, all "Register / Sign up" links removed
      (header, login page, verify-email page). Login page shows demo creds.
- [x] README updated: demo-only framing, JAVA101 as sandbox course, no
      sign-up, privilege-escalation note. Corrected auth (DRF token, not JWT).

### Security fixes (with tests)
- [x] **CRITICAL** — `is_instructor` made read-only in `UserSerializer`
      (was writable via `PATCH /api/auth/profile/` → self-promotion to
      instructor with read access to every course).
- [x] **HIGH** — IP-based `AnonRateThrottle` on anonymous traffic
      (login/registration/password-reset brute-force guard), env-gated via
      `THROTTLE_ANON` (off in tests/local, `30/min` in prod).
- [x] **HIGH** — demo account's password change blocked
      (`ProtectedPasswordChangeSerializer` keyed on `DEMO_ACCOUNT_EMAIL`) so
      one visitor can't lock the demo out for everyone.
- [x] **HIGH** — Django bumped 4.2.17 → 4.2.30 (last 4.2.x; picks up the
      4.2.18–4.2.30 security releases).
- [x] **MED** — avatar upload size cap (`AVATAR_MAX_UPLOAD_BYTES`, 5 MB),
      enforced in the view before storage.
- [x] **MED** — `/admin/` path configurable via `ADMIN_URL` (prod moves it
      off the default; set in dashboard, not committed).
- [x] **LOW** — lesson attachments: `svg`/`html` dropped from the extension
      whitelist (stored-XSS vector).
- [x] **LOW** — `/api/health/?deep=1` no longer leaks the raw DB exception
      (Neon host/user/SSL) to anonymous callers; logged server-side instead.
- [x] **LOW** — HSTS raised 3600s → 1 year (real domain is live).

## Verification
- [x] `/verify-stack` PASS — backend 389 passed (Django 4.2.30, Docker),
      `tsc` 0 errors, lint 0 errors / 22 warnings (baseline).
- [x] New tests: registration disabled (403 + no-instructor payload),
      profile can't self-promote, demo password-change blocked, regular
      password-change allowed, oversized avatar rejected, health deep-check
      no longer leaks DB detail.

## Deferred (operator action / larger changes — not in this phase)
- Lesson attachments are world-readable on the public R2 domain — move to a
  private bucket with signed URLs (infra change).
- Auth tokens never expire — consider knox/JWT with short TTLs (auth migration).
- Password-reset emails print to Render logs (console backend) — configure
  real SMTP (needs credentials).
- `ACCOUNT_EMAIL_VERIFICATION=optional` — moot while registration is off;
  revisit if signup is ever re-enabled.
- Verify `instructor@demo.com` (from `seed_data`, password `Admin123!`) does
  not exist in the production Neon DB.

## New env vars (set before/at deploy)
- `ALLOW_REGISTRATION=false` (render.yaml, committed)
- `THROTTLE_ANON=30/min` (render.yaml, committed)
- `ADMIN_URL` (render.yaml, `sync: false` — set the real path in the Render dashboard)
- `DEMO_ACCOUNT_EMAIL` — optional; defaults to `jdoe@demo.com`
