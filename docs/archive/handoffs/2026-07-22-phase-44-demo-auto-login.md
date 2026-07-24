# Handoff: Phase 44 — one-click demo auto-login

## Current state
Phase 44 code DONE on branch `feat/phase-44-demo-auto-login`, PR
https://github.com/Cesar6060/LMS/pull/35 — **stacked on PR #34** (phase 43
JWT work, base = `feat/phase-43-security-hardening`; GitHub retargets to
main when #34 merges). Delivered: `POST /api/auth/demo-login/`
(accounts/views.py::demo_login, AllowAny, ScopedRateThrottle scope
`demo_login`, mounted in accounts/urls.py before dj_rest_auth) issues the
JWT pair for settings.DEMO_ACCOUNT_EMAIL via RefreshToken.for_user; 404
when unseeded or inactive. `DEMO_ACCOUNT_PASSWORD` +
`THROTTLE_DEMO_LOGIN` settings (env-gated, defaults keep dev/tests
unchanged); seed_demo_account reads both from settings. Frontend:
`authService.demoLogin()`, `loginAsDemo()` in AuthContext, header button
(Header.tsx, spinner + /login fallback) and login-card secondary button
(LoginPage.tsx, credentials hint box deleted). README credential table
replaced with "click Try the demo". render.yaml: THROTTLE_DEMO_LOGIN
10/min + DEMO_ACCOUNT_PASSWORD sync:false. verify-stack PASS: backend
**415 passed** (was 409), tsc 0 errors, lint 0 errors / 22 warnings
(baseline). Curl-verified locally: POST → access/refresh/user, GET → 405,
Bearer token authenticates /api/auth/user/.

## In progress / not done
- Browser click-through of the two demo buttons (spec manual items 2/3/5)
  — Chrome extension wasn't connected; API + source-level equivalents
  verified. Silence convention applies if the user clicks through.
- Prod rollout section of the spec (post-merge, order matters — see PR).

## Next steps
1. Merge PR #34 (phase 43) following its deploy sequence, then PR #35
   retargets to main.
2. Render dashboard: set `DEMO_ACCOUNT_PASSWORD` to a generated secret
   (render.yaml now requires it — sync:false), merge #35.
3. After deploy: `DATABASE_URL=<neon> python manage.py seed_demo_account`
   to rotate the stored hash.
4. Verify live: demo button logs in; `POST /api/auth/login/` with
   jdoe@demo.com / Admin123! fails.

## Decisions made
- FBV kept (codebase style); ScopedRateThrottle scope set via
  `demo_login.cls.throttle_scope` since @api_view has no scope decorator.
- Throttle test monkeypatches `ScopedRateThrottle.THROTTLE_RATES` — DRF
  snapshots rates onto the class at import, so override_settings can't
  reach them.
- Added `DEMO_ACCOUNT_PASSWORD` (sync:false) to render.yaml beyond the
  spec's list — mirrors the ADMIN_URL pattern and forces rollout step 1.
- README "Try it" table removed (spec goal: password out of public view);
  local seed_data accounts in README §155 kept — they're local-only.
- Login-card demo button navigates to redirectTo (not hardcoded
  /dashboard) so ?next= deep links survive; header button → /dashboard.

## Gotchas discovered
- Login-card demo button sits inside the <form> — needs type="button" or
  it submits the form.
- The user's screenshot rework (deleted/renamed docs/screenshots/*) is
  uncommitted working-tree state — deliberately left out of the commit.

## Files to read first
- docs/specs/phase-44-demo-auto-login.md — checklist state + rollout
- backend/accounts/views.py — demo_login + throttle_scope note
- backend/accounts/tests.py — TestDemoLogin (throttle patch pattern)
- PR #35 body — deploy ordering
