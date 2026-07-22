# Handoff: Phase 42 — demo lockdown + security hardening (PR #33 open)

## Current state

Phase 42 code is DONE on branch `feat/phase-42-demo-lockdown-security`,
PR https://github.com/Cesar6060/LMS/pull/33 (base: LMS main). Phase 41
(#32) is already merged. This phase: (1) locks the live site to the shared
`jdoe@demo.com` demo student — no self-registration — and (2) fixes the
security issues a visitor could reach with the published demo password.

`/verify-stack` PASS: backend 389 passed (Django 4.2.30, Docker), tsc 0
errors, lint 0 errors / 22 warnings (baseline). No migrations.

Key changes:
- Registration gated behind `ALLOW_REGISTRATION` (default off) → 403,
  allauth registration urls never mounted. Frontend `/register` removed.
- CRITICAL fix: `is_instructor` now read-only in `UserSerializer` (was
  writable via `PATCH /api/auth/profile/` → self-promote to instructor).
- `AnonRateThrottle` (env `THROTTLE_ANON`), demo password-change blocked,
  Django 4.2.17→4.2.30, avatar size cap, `ADMIN_URL`, svg/html dropped from
  attachment whitelist, health no longer leaks DB error, HSTS 1yr.

## In progress / not done

Production rollout — blocked on Cesar merging PR #33 (never auto-merge).

## Next steps

1. Merge PR #33 (Cesar merges — deploys backend via Render, frontend via
   Cloudflare).
2. Before/at merge, set env in the **Render dashboard**:
   - `ADMIN_URL` (render.yaml is `sync: false`) — real admin path, must end
     with `/`. If unset, falls back to `admin/`.
   - `ALLOW_REGISTRATION=false` and `THROTTLE_ANON=30/min` are committed in
     render.yaml (auto-applied) — no action needed.
3. After deploy, verify at https://stemquest.cesarvillarreal11.workers.dev:
   - No Register button; `/register` redirects to login.
   - Log in as jdoe → `PATCH /api/auth/profile/ {"is_instructor":true}`
     returns is_instructor:false (privilege escalation closed).
   - `POST /api/auth/registration/` → 403.
   - Check https://stemquest-api.onrender.com/api/health/?deep=1 → ok.

## Decisions made

- New scope on top of merged phase 41, so a new branch + PR #33 (not a
  reopen of #32) and a new spec phase-42.
- Registration lockdown is server-side + frontend, not UI-only, because
  hiding the button alone is the exact hole the audit flagged.
- Throttling env-gated (off by default) so the 389-test suite and local dev
  aren't rate-limited; production sets `THROTTLE_ANON`.
- `is_instructor` fix is a read_only_fields change, not a view guard, so it
  holds for any future serializer caller.

## Deferred (operator action / larger, NOT in this PR)

- Lesson attachments world-readable on public R2 → private bucket + signed URLs.
- Non-expiring auth tokens → knox/JWT short TTLs.
- Password-reset mail prints to Render logs (console backend) → real SMTP.
- Verify `instructor@demo.com` (seed_data, `Admin123!`) is absent from prod Neon.

## Gotchas discovered

- Backend runs Django in Docker; the image needed `docker compose build
  backend` to pick up 4.2.30 (a plain restart keeps the old wheel).
- The go-forward repo is `Cesar6060/LMS` (remote `lms`); `origin` is the
  archived `dev-learning-platform`. Push/PR against `lms`.
- This shell aliases `head` to a curl tool — avoid piping to `head`.

## Files to read first

- `docs/specs/phase-42-demo-lockdown-security.md` — full checklist + deferred
- `backend/accounts/serializers.py` — is_instructor read-only, demo pw guard
- `backend/accounts/urls.py` + `views.py` — registration gate / 403 stub
- `backend/config/settings.py` — ALLOW_REGISTRATION, THROTTLE_ANON, ADMIN_URL
