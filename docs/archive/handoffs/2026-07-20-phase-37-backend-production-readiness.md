# Handoff: Phase 37 — Backend production readiness (code only)

## Current state
Phase 37 **implemented + verified**, PR #22 open against `lms/main`
(https://github.com/Cesar6060/LMS/pull/22) from branch
`feat/phase-37-backend-production-readiness`, cut from fresh `lms/main` @
`6b97525` (after PR #21 merged). Commits: `f5c06da` (implementation),
`8c7b3e5` (checklist).

The backend is deployable to Render + Neon **without having been deployed**.
Every new behaviour is inert unless its env var is set — `docker compose up`
behaves exactly as before.

- `backend/config/settings.py`
  - `DEBUG` default flipped to **False**; `INSECURE_SECRET_KEY` hoisted to a
    module constant; guard raises `ImproperlyConfigured` when `DEBUG` is false
    and `SECRET_KEY` is unset/insecure or `ALLOWED_HOSTS` is empty.
  - `DATABASE_URL` (optional) → `dj_database_url.parse(conn_max_age=600,
    conn_health_checks=True, ssl_require=True)` overrides the `DB_*` dict. The
    `DB_*` branch got **no** `CONN_MAX_AGE` — that would change dev behaviour.
  - WhiteNoise middleware directly after `SecurityMiddleware`; new `STORAGES`
    block picks `CompressedManifestStaticFilesStorage` only when `DEBUG` is
    false, plain `StaticFilesStorage` otherwise. `STATIC_URL` → `/static/`.
    `default` (media) stays `FileSystemStorage` — R2 is Phase 39.
  - Opt-in `USE_HTTPS` block (proxy SSL header, redirect, secure cookies, 1h
    HSTS, nosniff, `same-origin` referrer). `CSRF_TRUSTED_ORIGINS` is read
    unconditionally with an empty default. Removed the unused `import os`.
- `backend/config/health.py` (new) — plain Django view, `@never_cache`.
  Shallow `{"status": "ok"}` by default; `?deep=1` runs `SELECT 1` and returns
  **503** on any exception. `config/urls.py` now imports it and uses
  `path('api/health/', health, name='health')` — the byte-identical URL in the
  same position, replacing the inline `__import__` lambda.
- `render.yaml` (new, root) — `stemquest-api`, python/free/oregon,
  `rootDir: backend`, `branch: main`. Build = pip install + collectstatic;
  start = gunicorn 2 workers/120s. **No `migrate`** and no `databases:` key.
  `healthCheckPath: /api/health/` (shallow). 7 secrets `sync: false`.
  Header comment names Phase 38 as the consumer so nobody thinks it is live.
- `.github/workflows/ci.yml` — backend job gains a `collectstatic` step before
  `pytest` and `SECRET_KEY: ci-test-secret-key-not-for-production` on both.
  `DEBUG` deliberately left unset, so **CI now runs the suite under
  `DEBUG=False`**.
- `backend/requirements.txt` — `dj-database-url==2.3.0`, `gunicorn==23.0.0`,
  `whitenoise[brotli]==6.8.2`. `Dockerfile.prod:18` drops the ad-hoc
  ` gunicorn` from its `pip install`.
- `.env.example` — `DATABASE_URL`/`USE_HTTPS`/`CSRF_TRUSTED_ORIGINS` added as
  commented production-only keys; flipped `DEBUG` default documented; the
  `DB_HOST` `localhost`-vs-`db` drift explained.

**No frontend changes. No model changes, no migrations** (`makemigrations
--check` → "No changes detected").

### Verification
- `/verify-stack` **PASS**: pytest **354 passed** (346 existing + 8 new, zero
  regressions), `tsc --noEmit` **0 errors**, lint **0 errors / 22 warnings**
  (= baseline).
- Suite re-run under CI's exact env (`DEBUG` unset → False + dummy
  `SECRET_KEY`): **354 passed**. The spec's `DEBUG: 'True'` fallback was
  **not needed** — no test depends on `DEBUG=True`.
- CI on PR #22 (run `29789922495`): backend **pass** 2m53s, frontend **pass**
  39s.
- `check --deploy` with `DEBUG=False USE_HTTPS=True ALLOWED_HOSTS=example.com`
  and a realistic 50-char key → **only** `security.W021` (HSTS preload),
  deliberate until Phase 39 confirms the domain. No W004/W006/W008/W012/W016.
  (A short throwaway key also trips `W009` — artifact of the key, not the
  settings.)
- `check` with the normal dev env → "no issues (0 silenced)".
- Guard proven: `-e DEBUG=False -e SECRET_KEY=` and `env -u SECRET_KEY` both
  raise `ImproperlyConfigured: SECRET_KEY must be set when DEBUG is False.`
  and **exit 1**.
- `collectstatic --noinput` under `DEBUG=False`: 767 post-processed,
  `staticfiles.json` 13808 bytes.
- `render.yaml` parses (js-yaml via the frontend container).
- Dev unchanged after a full `down`/`up -d`: frontend 200, `/admin/` 302s to
  `/admin/login/` over **plain http** (no HTTPS redirect),
  `/static/admin/css/base.css` 200 `text/css` 21310 bytes, `/api/health/` ok
  and `?deep=1` → `{"status": "ok", "database": "ok"}`.

## In progress / not done
- **PR #22 not merged** — the user's call, as in prior phases.
- **Neon password not rotated** (project `ep-falling-frog-avzgk4ed`, db
  `neondb`). Still open; the new connection string is entered into Render's
  dashboard in Phase 38, never committed.
- **Manual click-through not done** — instructor login → course → Learning
  Mode. Only the HTTP-level half was automated (see above). Spec item left
  unchecked.

## Next steps
1. Review + merge PR #22; confirm the `push`-to-`main` run is green.
2. Rotate the Neon password, note the connection string privately.
3. Do the click-through and check off the "Dev is unchanged" spec item.
4. Delete the merged `feat/phase-36-github-actions-ci` branch.
5. Start **Phase 38 — Render + Neon deploy**: point Render at `render.yaml`,
   fill the 7 `sync: false` secrets, then run `migrate` +
   `createsuperuser` + `populate_java_course` **by hand in the Render shell**
   (migrations are deliberately not in the blueprint).

## Decisions made
- **Deviation from the spec's guard.** As specced, the guard compared only
  against `INSECURE_SECRET_KEY` — and the spec's own verification one-liner
  (`-e SECRET_KEY=`) **passed** against it, because decouple reads an
  explicitly-empty env value as `''`, which is neither the insecure default
  nor a usable key. A misconfigured prod boot would have sailed through.
  Guard is now `if not SECRET_KEY or SECRET_KEY == INSECURE_SECRET_KEY:`.
- `SECRET_KEY` left as `sync: false` in `render.yaml` per the spec, though
  Render also supports `generateValue: true` (key never leaves their vault).
  Offered to the user; not changed unilaterally after already deviating once.
- Ran the full suite under `DEBUG=False` locally *before* pushing rather than
  discovering the blast radius in CI — the `DEBUG` flip was the phase's
  riskiest change and the one thing that could redden every test at
  collection.
- `SECURE_*` gated on `USE_HTTPS`, never on `not DEBUG` — otherwise CI (which
  now runs `DEBUG=False`) would hit HTTPS redirects on every request.

## Gotchas discovered
- **`backend/Dockerfile.prod:29` runs `collectstatic` at build time with no
  `SECRET_KEY`**, so with the flipped `DEBUG` default that image build now
  hits the guard. Out of scope this phase (Phase 40 marks those files
  superseded), but it is a live trap — the dev `backend/Dockerfile:24` only
  survives because it ends in `|| true`.
- `staticfiles.json` does **not** appear in the host `backend/staticfiles/`:
  compose mounts the `backend_static` **named volume** over `/app/staticfiles`,
  masking the bind mount. Check it at `/app/staticfiles/` inside the container.
  (`staticfiles/` is gitignored, so nothing leaks into commits.)
- The manifest only exists when `DEBUG=False` — that is the branch selecting
  WhiteNoise storage. Running `collectstatic` with compose's default
  `DEBUG=True` writes no manifest.
- No `pytest` or `python` on the host (zsh: `python3` is 3.14 with no pytest);
  run the suite via `docker compose exec -T backend python -m pytest`.
- zsh still shadows `head` with an HTML tool — use `tail`/`sed`/Read instead.
- Pre-existing working-tree dirt left untouched: 7 deleted
  `docs/screenshots/*.png` and a modified `frontend/tsconfig.tsbuildinfo`.

## Files to read first
- `docs/specs/phase-37-backend-production-readiness.md` — 3 items open, each
  annotated with what was actually verified
- `docs/specs/deployment-overview.md` — 36–40 roadmap
- `render.yaml` — the artifact Phase 38 consumes
- `backend/config/settings.py` — guard (~l.20-33), `DATABASE_URL` (~l.95),
  `STORAGES` (~l.125), `USE_HTTPS` (~l.165)
