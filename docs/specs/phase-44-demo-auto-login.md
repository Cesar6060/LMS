# Phase 44 — Demo auto-login (one-click "Try the demo")

## Goal

Replace the published demo credentials on the login page with a one-click
demo experience: the "Try the demo" button (header and login card) logs the
visitor in as the shared demo student (`jdoe@demo.com` / Jordan Doe) via a
new backend endpoint that issues JWTs server-side, so the demo password
disappears from public view entirely. The password is simultaneously moved
out of source into an env var (`DEMO_ACCOUNT_PASSWORD`) and rotated to a
secret value in production, closing the last hole where a visitor could log
in with raw credentials.

## Out of scope

- Renaming the demo user (stays Jordan Doe).
- Per-visitor sandboxed demo accounts or automatic demo-data reset jobs
  (reset remains the manual `seed_demo_account --reset`).
- An instructor-role demo account.
- Any change to the JWT/refresh flow from phase 43 (demo login returns the
  same token pair and rides the existing interceptor).
- httpOnly-cookie token transport (still explicitly deferred).
- Removing/redesigning anything else on the login card (form, forgot
  password, etc.).

## Backend tasks

- [x] `settings.py`: add `DEMO_ACCOUNT_PASSWORD = config('DEMO_ACCOUNT_PASSWORD', default='Admin123!')`
      next to `DEMO_ACCOUNT_EMAIL`. Default keeps local dev/test unchanged.
- [x] `seed_demo_account.py`: replace the hardcoded `DEMO_PASSWORD`
      constant with `settings.DEMO_ACCOUNT_PASSWORD` (and `DEMO_EMAIL` with
      `settings.DEMO_ACCOUNT_EMAIL` if trivial). `--reset` keeps working.
- [x] New view `accounts/views.py::demo_login`:
      - `POST /api/auth/demo-login/` (add to `accounts/urls.py` **before**
        the `dj_rest_auth.urls` include), permission `AllowAny`, no body.
      - Looks up the active user with `email=settings.DEMO_ACCOUNT_EMAIL`;
        404 with a clear detail message if absent (e.g. seed not run).
      - Issues tokens via `rest_framework_simplejwt.tokens.RefreshToken.for_user`
        — never touches the password.
      - Response shape matches what the frontend already consumes from
        dj-rest-auth login: `{ "access": ..., "refresh": ..., "user": UserSerializer }`.
      - GET/other methods → 405.
- [x] Throttling: `ScopedRateThrottle` scope `demo_login`, rate from
      `config('THROTTLE_DEMO_LOGIN', default=None)` (same env-gated pattern
      as `THROTTLE_ANON` so the test suite is unaffected). Add
      `THROTTLE_DEMO_LOGIN: "10/min"` to `render.yaml`.
- [x] `.env.example`: document `DEMO_ACCOUNT_PASSWORD` and
      `THROTTLE_DEMO_LOGIN`.
- [x] Tests (`accounts/tests.py`):
      - [x] POST returns 200 with `access`, `refresh`, and
            `user.email == DEMO_ACCOUNT_EMAIL`; access token authenticates
            a follow-up `GET /api/auth/user/`.
      - [x] Demo user is a student in the response (`is_instructor` false).
      - [x] 404 when no demo user exists.
      - [x] 404 (not a 500, and no token issued) when the demo user exists
            but `is_active=False`.
      - [x] GET → 405.
      - [x] With `THROTTLE_DEMO_LOGIN` set (override_settings), requests
            over the rate → 429.
      - [x] Existing demo password-change guard still passes (regression).

## Frontend tasks

- [x] `services/auth.ts`: `demoLogin(): Promise<AuthResponse>` — POST
      `/auth/demo-login/`, store `access`/`refresh` in localStorage exactly
      like `login()`.
- [x] `contexts/AuthContext.tsx`: `loginAsDemo()` — calls
      `authService.demoLogin()` then `refreshUser()`; expose via context
      (mirror `login`'s shape).
- [x] `components/layout/Header.tsx` (~line 315): "Try the demo" becomes a
      `<Button>` with an onClick handler (drop the `<Link to="/login">`):
      disabled + spinner/label change while pending, then
      `navigate('/dashboard')` on success. On failure, fall back to
      navigating to `/login` (the form still works) — no dead click.
- [x] `pages/auth/LoginPage.tsx` (lines 114-119): delete the credentials
      hint box; in its place render a secondary-variant "Try the demo"
      button (full-width, under Sign in, small "Just exploring?" lead-in
      text) wired to the same `loginAsDemo()` + navigate flow, with
      pending/disabled state and the page's existing error display on
      failure.
- [x] No new types needed if the endpoint reuses `AuthResponse`; adjust
      `types/index.ts` only if the shape differs.

## Verification

- [x] `/verify-stack` passes: backend pytest **415 passed** (409 baseline
      + 6 demo-login tests), `npx tsc --noEmit` 0 errors, lint 0 errors /
      22 warnings (baseline).
- [x] Manual flow (local, `docker compose up -d`, seed run) — items 1 & 4
      verified directly (grep of `frontend/src` + the served LoginPage
      module found zero credential strings; curl POST returned
      access/refresh/user for jdoe@demo.com and GET returned 405, Bearer
      access token authenticated `/api/auth/user/`). Items 2/3/5 (browser
      click-through) pending a human pass — Chrome extension was not
      connected during implementation.
      1. Logged out, on `/login`: no credentials visible anywhere on the
         page or in page source.
      2. Click header "Try the demo" → land on `/dashboard` as Jordan Doe
         (student view, no instructor nav).
      3. Log out, click the login-card demo button → same result.
      4. `POST /api/auth/demo-login/` via curl returns access/refresh;
         GET → 405.
      5. Refresh the page after demo login → still authenticated (tokens
         persisted, interceptor refresh path untouched).
- [ ] Prod rollout (after merge — ORDER MATTERS):
      1. Render dashboard: set `DEMO_ACCOUNT_PASSWORD` to a generated
         secret (and confirm `THROTTLE_DEMO_LOGIN` from render.yaml).
      2. Re-run `seed_demo_account` against prod (Render shell or
         `DATABASE_URL=<neon> python manage.py seed_demo_account`) so the
         stored hash rotates.
      3. Verify live: demo button logs in; `POST /api/auth/login/` with
         `jdoe@demo.com / Admin123!` now fails; existing visitor sessions
         unaffected (JWTs unchanged).

## Notes / decisions from planning interview

- Backend endpoint chosen over frontend-hardcoded credentials so the
  password leaves the client bundle entirely.
- Password rotated in prod via env var; local default stays `Admin123!` so
  dev and tests need no new setup.
- Demo user stays "Jordan Doe" — no re-seed for naming.
- Login card keeps a demo entry point (secondary button) so visitors who
  land directly on `/login` aren't dependent on noticing the header.
