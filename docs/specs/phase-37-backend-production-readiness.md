# Phase 37 — Backend production readiness (code only)

## Goal

Make the Django backend deployable to Render + Neon **without deploying it**.
Every change lands in the repo and is exercised by `/verify-stack` and CI, but
each new production behaviour stays **inert unless its env var is set**, so
`docker compose up` on this laptop behaves exactly as it does today. Concretely:
optional `DATABASE_URL` (Neon, SSL, connection reuse) alongside the existing
`DB_*` settings; WhiteNoise so gunicorn can serve `/admin/` CSS with no nginx;
opt-in `SECURE_*` / `CSRF_TRUSTED_ORIGINS` hardening; a real `/api/health/`
view replacing the placeholder lambda; a fail-fast guard so a misconfigured
production boot crashes loudly instead of running with a public `SECRET_KEY`;
gunicorn pinned in `requirements.txt`; a `render.yaml` blueprint Phase 38 can
point Render at; and a refreshed root `.env.example`. Ends with the Neon
password rotated in Neon's console — noted, not committed, used in Phase 38.

## Out of scope

- Creating or configuring **anything** in the Render / Neon / Cloudflare
  dashboards beyond the Neon password rotation. No service, no deploy, no env
  vars set in a dashboard — that is Phase 38.
- Running migrations against Neon, `createsuperuser`, `populate_java_course`.
- `django-storages` / R2 media, `frontend/public/_redirects`, the frontend
  `VITE_API_URL` prod guard — all Phase 39.
- OpenTelemetry / Grafana wiring, Sentry `environment=`/`release=` tags — Phase 40.
- Deleting or editing `docker-compose.prod.yml`, `nginx/`, `frontend/nginx.conf`,
  `backend/Dockerfile.prod` beyond the one gunicorn-pin line below. Marking them
  superseded is Phase 40.
- Splitting `config/settings.py` into a `settings/` package. Four files hardcode
  `DJANGO_SETTINGS_MODULE = config.settings` (`pytest.ini`, `manage.py`,
  `wsgi.py`, `asgi.py`); env-var-driven config stays the mechanism.
- Splitting the root `.env` into `backend/.env` + `frontend/.env`, and removing
  the dead `VITE_WS_URL` / `REDIS_URL` keys. (Decided: refresh `.env.example`
  only; leave the live `.env` layout alone so decouple + compose keep working.)
- Adding a `conftest.py` to de-duplicate the per-file pytest fixtures.
- Any change to `backend/*/models.py` — **this phase adds no migrations**.

## Decisions from the scoping interview (2026-07-20)

1. **Health check**: shallow by default (`{"status": "ok"}`, no DB hit) so a
   cold Neon branch can't fail a Render deploy gate; `?deep=1` adds a
   `SELECT 1` and returns **503** on failure.
2. **Migrations on deploy**: **manual**. `render.yaml` never runs `migrate`;
   the build command is pip install + collectstatic, the start command is
   gunicorn. Phase 38 runs `migrate` by hand in the Render shell, in the same
   session as `createsuperuser` + `populate_java_course`.
3. **Config guards**: `DEBUG` default flips to **False**. When `DEBUG` is false,
   raise `ImproperlyConfigured` at import if `SECRET_KEY` is still the insecure
   default or `ALLOWED_HOSTS` is empty.
4. **Env files**: refresh the root `.env.example` only.

### Derived constraint — do not break CI or dev

Flipping the `DEBUG` default is the riskiest change in the phase. Three
consumers read settings with **no env vars at all**:

- **CI** (`.github/workflows/ci.yml`) sets only `DB_HOST=localhost`. With the
  new default it would boot `DEBUG=False`, hit the `SECRET_KEY` guard, and
  every test would error at collection.
- **`cd backend && pytest`** on this laptop reads the root `.env` via
  decouple's upward search. Confirm that file sets `DEBUG=True`.
- **`docker compose up`** already passes `DEBUG=True` explicitly
  (`docker-compose.yml:34`) — unaffected.

Therefore the `SECURE_*` block must be gated on its **own** env var, never on
`not DEBUG`, so tests can run with `DEBUG=False` without triggering HTTPS
redirects. CI gets a dummy `SECRET_KEY` and keeps `DEBUG` unset, so the test
suite exercises the production-ish path. If tests turn out to depend on
`DEBUG=True`, fall back to setting `DEBUG: 'True'` on the CI job and record
that in the handoff.

## Backend tasks

### Dependencies

- [x] `backend/requirements.txt`: add `dj-database-url==2.3.0`,
      `whitenoise[brotli]==6.8.2`, `gunicorn==23.0.0` — `==`-pinned like every
      other entry except `requests`.
- [x] `backend/Dockerfile.prod:18`: drop the trailing ad-hoc ` gunicorn` from
      the `pip install` now that it is pinned in `requirements.txt`.
- [x] Rebuild so the dev image has the new packages:
      `docker compose build backend && docker compose up -d`.

### `backend/config/settings.py`

- [x] Remove the unused `import os` (line 5). Add
      `from django.core.exceptions import ImproperlyConfigured` and
      `import dj_database_url`.
- [x] Hoist the insecure key to a module constant so the guard can compare
      against it, then flip the `DEBUG` default:
      ```python
      INSECURE_SECRET_KEY = 'django-insecure-dev-key-change-in-production'
      SECRET_KEY = config('SECRET_KEY', default=INSECURE_SECRET_KEY)
      DEBUG = config('DEBUG', default=False, cast=bool)
      ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

      if not DEBUG:
          if SECRET_KEY == INSECURE_SECRET_KEY:
              raise ImproperlyConfigured(
                  'SECRET_KEY must be set when DEBUG is False.')
          if not ALLOWED_HOSTS:
              raise ImproperlyConfigured(
                  'ALLOWED_HOSTS must be set when DEBUG is False.')
      ```
- [x] `MIDDLEWARE` (lines 50-60): insert
      `'whitenoise.middleware.WhiteNoiseMiddleware'` **immediately after**
      `SecurityMiddleware` and before `SessionMiddleware`. Order matters —
      WhiteNoise must precede everything that could short-circuit a static hit.
- [x] `DATABASES` (lines 83-92): keep the existing `DB_*` dict as the default;
      when `DATABASE_URL` is set, let it win. Inert without the env var:
      ```python
      DATABASE_URL = config('DATABASE_URL', default='')
      if DATABASE_URL:
          DATABASES['default'] = dj_database_url.parse(
              DATABASE_URL,
              conn_max_age=600,
              conn_health_checks=True,
              ssl_require=True,
          )
      ```
      `ssl_require=True` is what Neon needs. Do **not** add `CONN_MAX_AGE` to
      the `DB_*` branch — persistent connections against the local compose
      Postgres would change dev behaviour.
- [x] Static files (lines 109-110): normalise `STATIC_URL` to `'/static/'`,
      keep `STATIC_ROOT`, and add a `STORAGES` block whose `staticfiles`
      backend is WhiteNoise's `CompressedManifestStaticFilesStorage` when
      `DEBUG` is false and Django's default `StaticFilesStorage` when true.
      Leave `default` (media) on `FileSystemStorage` — R2 is Phase 39.
      Manifest storage raises if `staticfiles.json` is missing, which is why
      CI gains a `collectstatic` step below.
- [x] New **opt-in HTTPS hardening** block, gated on its own flag so it is
      inert locally and in CI:
      ```python
      USE_HTTPS = config('USE_HTTPS', default=False, cast=bool)
      CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

      if USE_HTTPS:
          SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
          SECURE_SSL_REDIRECT = True
          SESSION_COOKIE_SECURE = True
          CSRF_COOKIE_SECURE = True
          SECURE_HSTS_SECONDS = 3600          # deliberately short until 39 is verified
          SECURE_HSTS_INCLUDE_SUBDOMAINS = True
          SECURE_CONTENT_TYPE_NOSNIFF = True
          SECURE_REFERRER_POLICY = 'same-origin'
      ```
      `SECURE_PROXY_SSL_HEADER` is mandatory — Render terminates TLS and
      forwards `X-Forwarded-Proto`; without it `SECURE_SSL_REDIRECT` loops.
      `CSRF_TRUSTED_ORIGINS` is read unconditionally (empty default) because
      `/admin/` needs it even before HTTPS redirects are on, and
      `CORS_ALLOW_CREDENTIALS = True` is already set at line 141.
      HSTS stays at 1 hour this phase; raising it is a Phase 39 decision once
      the real domain is confirmed working.

### `/api/health/`

- [x] New `backend/config/health.py`. Do **not** put it in `backend/core/` —
      that package holds `email.py` and is not in `INSTALLED_APPS`.
      ```python
      from django.db import connection
      from django.http import JsonResponse
      from django.views.decorators.cache import never_cache


      @never_cache
      def health(request):
          if request.GET.get('deep') != '1':
              return JsonResponse({'status': 'ok'})
          try:
              with connection.cursor() as cursor:
                  cursor.execute('SELECT 1')
                  cursor.fetchone()
          except Exception as exc:
              return JsonResponse(
                  {'status': 'error', 'database': str(exc)}, status=503)
          return JsonResponse({'status': 'ok', 'database': 'ok'})
      ```
      A plain Django view, so DRF's global `IsAuthenticated`
      (`settings.py:126-134`) does not apply and the endpoint is public — this
      is now deliberate rather than accidental. Catch broad `Exception`: the
      point is to report *any* DB failure as 503, not to crash.
- [x] `backend/config/urls.py:30`: replace the inline
      `__import__`-based lambda with `path('api/health/', health,
      name='health')`, importing `health` at the top of the file. Keep the URL
      string byte-identical and keep it in the same position, and preserve the
      ordering comment at lines 14-21 — the pattern only resolves because
      neither `quizzes.urls` nor `discussions.urls` defines `health/`.

### `render.yaml` (root)

- [x] New blueprint. No `databases:` key — Postgres is Neon, external to
      Render. Every secret is `sync: false` (prompted in the dashboard, never
      committed).
      - `type: web`, `name: stemquest-api`, `env: python`, `plan: free`,
        `region: oregon`, `rootDir: backend`, `branch: main`.
      - `buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput`
      - `startCommand: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
      - **No `migrate`** — per decision 2 it is manual in the Render shell.
      - `healthCheckPath: /api/health/` (the shallow path — no query string,
        so no DB dependency in the deploy gate).
      - `envVars`: `PYTHON_VERSION: 3.12` (match CI), `DEBUG: false`,
        `USE_HTTPS: true`, `EMAIL_BACKEND: console`,
        `ACCOUNT_EMAIL_VERIFICATION: optional`, and `sync: false` entries for
        `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`,
        `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`,
        `SENTRY_DSN`.
- [x] Add a comment at the top naming Phase 38 as the phase that consumes this
      file, so nobody assumes it is live.

### `.env.example` (root)

- [x] Add, with comments marking each as **production-only, leave unset for
      local dev**: `DATABASE_URL`, `USE_HTTPS`, `CSRF_TRUSTED_ORIGINS`.
- [x] Document the flipped `DEBUG` default: unset now means **False**, and
      local dev needs `DEBUG=True` explicitly.
- [x] Fix the `DB_HOST` drift — the file says `localhost`, docker-compose needs
      `db`. Note both and which applies when.
- [x] `FRONTEND_URL` is documented here but missing from the live `.env`; keep
      it documented with the localhost default called out.
- [x] Leave the `VITE_*` keys where they are (out of scope this phase).

### Local `.env` + Neon (user actions, no commit)

- [x] Confirm the root `.env` sets `DEBUG=True`; add it if absent — otherwise
      bare `cd backend && pytest` will hit the new guard.
- [ ] Rotate the Neon password in the Neon console (project
      `ep-falling-frog-avzgk4ed`, db `neondb`). **Note the new connection
      string somewhere private — do not paste it into the repo, `.env.example`,
      or chat.** It gets entered into Render's dashboard in Phase 38.

### CI (`.github/workflows/ci.yml`)

- [x] Backend job: add `SECRET_KEY: ci-test-secret-key-not-for-production` next
      to the existing `DB_HOST: localhost` (ci.yml:51-53) so the new guard is
      satisfied with `DEBUG` left unset — i.e. CI now runs the suite under
      `DEBUG=False`.
- [x] Backend job: add a `python manage.py collectstatic --noinput` step in
      `backend` **before** `pytest`, so WhiteNoise's manifest storage has a
      `staticfiles.json`. This doubles as a check that the Render build
      command works.
- [ ] Fallback if the suite proves to depend on `DEBUG=True`: add
      `DEBUG: 'True'` to the same env block and note it in the handoff rather
      than weakening the guard.
      **Not needed.** The full suite was run under CI's exact conditions
      (`DEBUG` unset → False, `SECRET_KEY=ci-test-secret-key-not-for-production`)
      and returned **354 passed**. No test depends on `DEBUG=True`.

### Tests

New file `backend/config/tests/test_production_settings.py` — that package
already exists (`__init__.py` + `test_url_conf.py`) and is the precedent for
config-level tests. Follow its style: module-level functions, no
`@pytest.mark.django_db` unless the test actually needs the DB.

- [x] `test_health_shallow_ok` — `client.get('/api/health/')` → 200,
      `{'status': 'ok'}`, and **no** `database` key. No DB mark needed.
- [x] `test_health_deep_ok` — `@pytest.mark.django_db`,
      `/api/health/?deep=1` → 200, `database == 'ok'`.
- [x] `test_health_deep_returns_503_when_db_down` — monkeypatch
      `django.db.connection.cursor` to raise; assert 503 and
      `status == 'error'`.
- [x] `test_health_requires_no_auth` — unauthenticated `APIClient` still gets
      200, proving DRF's global `IsAuthenticated` does not reach this view.
- [x] `test_health_url_name_resolves` — `reverse('health') == '/api/health/'`,
      mirroring `test_url_conf.py`'s resolve-based approach.
- [x] `test_database_url_overrides_db_settings` — call
      `dj_database_url.parse(...)` on a fake `postgres://` URL and assert
      `ENGINE`, `NAME`, and `OPTIONS['sslmode'] == 'require'`. Do not mutate
      the live `DATABASES`.
- [x] `test_secure_settings_absent_by_default` — with `USE_HTTPS` unset,
      assert `getattr(settings, 'SECURE_SSL_REDIRECT', False)` is falsy. This
      is the regression test for "inert without env vars".
- [x] `test_whitenoise_middleware_follows_security_middleware` — assert
      WhiteNoise's index in `settings.MIDDLEWARE` is exactly
      `SecurityMiddleware`'s + 1.

## Frontend tasks

**None.** No `frontend/` source, type, or config changes in this phase — the
`VITE_API_URL` prod guard is Phase 39, and per the deployment overview it must
throw at **runtime**, not build time, or CI's `npm run build` step breaks.
`tsc`/`lint`/`build` must stay green purely as a no-regression check.

## Verification

- [x] `python manage.py check --deploy` inside the backend container with
      `DEBUG=False USE_HTTPS=True SECRET_KEY=<throwaway> ALLOWED_HOSTS=example.com`
      — expect **no `security.W00x` warnings** for SSL redirect, HSTS, secure
      cookies, or content-type nosniff. Paste the output into the handoff.
      Result: with a realistic 50-char key the **only** remaining warning is
      `security.W021` (HSTS preload), which is deliberate — HSTS stays at
      3600s until Phase 39 confirms the real domain. No W004/W006/W008/
      W012/W016. (With a short throwaway key you also get `W009`, an artifact
      of the test key, not of the settings.)
- [x] `python manage.py check` with the normal dev env — clean, no warnings
      introduced.
- [x] The guard actually guards: `DEBUG=False` with no `SECRET_KEY` must raise
      `ImproperlyConfigured` mentioning `SECRET_KEY`. Prove it with a
      one-liner, e.g.
      `docker compose exec -T -e DEBUG=False -e SECRET_KEY= backend python manage.py check`
      → non-zero exit. Show the traceback.
      **Deviation from the spec's code block.** As written, the guard only
      compared against `INSECURE_SECRET_KEY`, and this exact one-liner
      *passed* — decouple reads an explicitly-empty `SECRET_KEY=` as `''`,
      which is neither the insecure default nor a usable key, so a
      misconfigured boot would have sailed through. The guard is therefore
      `if not SECRET_KEY or SECRET_KEY == INSECURE_SECRET_KEY:`. Both paths
      now raise `ImproperlyConfigured: SECRET_KEY must be set when DEBUG is
      False.` and exit **1** (verified for `SECRET_KEY=` and for
      `env -u SECRET_KEY`).
- [x] `docker compose exec backend python manage.py collectstatic --noinput`
      succeeds and writes `backend/staticfiles/staticfiles.json`.
      Note: the manifest only appears when `DEBUG=False` (that is the branch
      that selects WhiteNoise's manifest storage), and it lands in the
      `backend_static` **named volume** that compose mounts over
      `/app/staticfiles`, not in the host `backend/staticfiles/` directory.
      Verified at `/app/staticfiles/staticfiles.json` (13808 bytes) after
      `-e DEBUG=False -e SECRET_KEY=...`; 767 files post-processed.
- [x] `pytest backend/config/tests/test_production_settings.py` — all new
      tests pass.
- [x] **`/verify-stack`** green: full `pytest` (**346 existing + the new
      config tests**, zero regressions), `npx tsc --noEmit` 0 errors,
      `npm run lint` **0 errors / 22 warnings** (the standing baseline — more
      warnings than that is a regression).
- [x] `render.yaml` parses as valid YAML. No host linter and no `pyyaml` in
      the backend image, so reuse the Phase 36 trick:
      `docker compose exec -T frontend sh -c 'cat > /tmp/r.yaml && npx --yes js-yaml /tmp/r.yaml' < render.yaml`
- [ ] **Dev is unchanged** — the real acceptance test for "inert". After a
      `docker compose down && docker compose up -d`: `http://localhost:5173`
      loads, log in as an instructor, open a course, open Learning Mode on a
      lesson. No HTTPS redirect, no CSRF failure, no missing admin CSS at
      `http://localhost:8000/admin/`.
      Automated half done after a full `down`/`up -d`: frontend 200,
      `/admin/` 302s to `/admin/login/` over **plain http** (no HTTPS
      redirect), `/static/admin/css/base.css` 200 `text/css` 21310 bytes,
      `/api/health/` ok. The instructor login → course → Learning Mode
      click-through is still the user's manual step.
- [x] `git status` shows **no migration files** — this phase touches no models.
- [x] Push the branch, open a PR against `lms/main`, both CI jobs green.
      (Merging is the user's call, as in prior phases.)
      PR #22, run `29789922495`: Backend (pytest) **pass** 2m53s, Frontend
      (tsc, lint, build) **pass** 39s. Merge still pending the user.
- [x] Neon password rotated and the new connection string noted privately —
      confirm in the handoff **without quoting it**.

## Suggested branch

`feat/phase-37-backend-production-readiness`, cut from fresh `lms/main` after
PR #21 (Phase 36) — already merged 2026-07-21, `main` CI run `29789086310`
green.
