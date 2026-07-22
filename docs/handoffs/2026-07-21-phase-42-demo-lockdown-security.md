# Handoff: Phase 42 — demo lockdown + security hardening

## Current state
Phase 42 code DONE on branch `feat/phase-42-demo-lockdown-security`, PR
https://github.com/Cesar6060/LMS/pull/33 open against LMS main (phase 41 #32
already merged). Locks the live site to the shared `jdoe@demo.com` demo
student (no self-registration) and fixes what a visitor could exploit with
the published demo password. Modified: `backend/accounts/{serializers,urls,
views,tests}.py`, `backend/config/{settings,urls,health}.py`,
`backend/config/tests/{test_production_settings,test_url_conf}.py`,
`backend/courses/views.py`, `backend/requirements.txt` (Django 4.2.17→4.2.30),
`frontend/src/App.tsx`, `.../components/layout/Header.tsx`,
`.../pages/auth/{LoginPage,VerifyEmailPage}.tsx`, `.env.example`,
`render.yaml`; deleted `.../pages/auth/RegisterPage.tsx`; added
`docs/specs/phase-42-demo-lockdown-security.md`. verify-stack PASS: backend
**395 passed** (Docker), tsc 0 errors, lint 0 errors / 22 warnings. No migrations.

## In progress / not done
Nothing half-finished in code. Production rollout blocked on Cesar merging
PR #33 (never auto-merge — merge deploys backend via Render + frontend via
Cloudflare).

## Next steps
1. In the **Render dashboard**, set `ADMIN_URL` (e.g. `secret-console/`, must
   end with `/`) — it's `sync: false`. `ALLOW_REGISTRATION=false` and
   `THROTTLE_ANON=30/min` are committed in render.yaml (auto-applied).
2. Merge PR #33.
3. After deploy verify: no Register button, `/register`→login,
   `PATCH /api/auth/profile/ {"is_instructor":true}` as jdoe returns
   `is_instructor:false`, `POST /api/auth/registration/`→403,
   https://stemquest-api.onrender.com/api/health/?deep=1 → ok.
4. Confirm `instructor@demo.com` (seed_data, `Admin123!`) is ABSENT from prod
   Neon — if present it's a live instructor login.

## Decisions made
- New branch + PR #33 + spec phase-42 (not a reopen of merged #32) since this
  is new scope on top of phase 41.
- Registration lockdown is server-side (403 stub, urls unmounted) + frontend,
  not UI-only — hiding the button was the exact hole the audit flagged.
- `is_instructor` fixed via `read_only_fields`, not a view guard, so it holds
  for any future serializer caller.
- Throttling env-gated (off by default) so the test suite/local dev aren't
  rate-limited.

## Gotchas discovered
- Django runs in Docker: needed `docker compose build backend` (not just
  restart) to pick up 4.2.30.
- Go-forward repo is `Cesar6060/LMS` (remote `lms`); `origin` is the archived
  `dev-learning-platform`. Push/PR against `lms`.
- This shell aliases `head` to a curl-like tool — avoid piping to `head`.

## Files to read first
- `docs/specs/phase-42-demo-lockdown-security.md` — checklist + deferred items
- `backend/accounts/serializers.py` — is_instructor read-only, demo pw guard
- `backend/accounts/urls.py` + `views.py` — registration gate / 403 stub
- `backend/config/settings.py` — ALLOW_REGISTRATION, THROTTLE_ANON, ADMIN_URL
