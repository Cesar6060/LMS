# Phase 59 — Django 4.2 → 5.2 LTS upgrade

## Goal

Upgrade the backend from Django 4.2.30 LTS to the latest Django 5.2.x LTS patch. This is a Django-only pin change: recon (2026-07-29) confirmed the codebase is already 5.x-shaped (dict-style `STORAGES`, `BigAutoField` everywhere, no removed APIs, no `index_together` in any of the 37 migrations) and every Django-sensitive third-party pin already supports 5.2 (DRF 3.17.1, allauth 65.18.0, dj-rest-auth 7.2.0, simplejwt 5.5.1, django-csp 4.0, django-storages 1.14.6, whitenoise 6.12.0, psycopg 3.3.4, pytest-django 4.12.0). Alongside the bump, make `RemovedInDjango60Warning` a hard error in pytest so 6.0-removed APIs can't creep in silently, and prove there is no schema drift against Neon prod — rehearsing on a Neon branch if any new migration appears.

## Out of scope

- Bumping any dependency other than Django (Dependabot handles minors/patches weekly; majors arrive as their own PRs).
- Python version change — stay on 3.12 everywhere (Dockerfiles, CI, Render `PYTHON_VERSION`). 3.13 becomes legal under 5.2 but is not this phase.
- Converting `unique_together` → `UniqueConstraint` (11 model Metas). Soft-deprecated only, no warning fires, and conversion would churn 7 migration files for zero benefit.
- Carried items from earlier phases: XP double-award schema fix, JAVA101 answer-rotation reseed, phase-56 regression click-through, school-device login test, Sentry LoginPage TypeError.
- Frontend changes of any kind.
- `Dockerfile.prod` cleanup (unused by Render; leave as-is).

## Backend tasks

- [x] Bump `Django==4.2.30` → `Django==5.2.16` in `backend/requirements.txt` (line 2). OSV query on 5.2.16 (2026-07-29): 0 advisories.
- [x] Rebuild and restart the stack: `docker compose build backend && docker compose up -d` — done; `django.get_version()` in container prints `5.2.16`.
- [x] `python manage.py makemigrations --check --dry-run` inside the container — "No changes detected". No migration rehearsal needed.
- [x] Added `error::django.utils.deprecation.RemovedInDjango60Warning` after the ignore lines in `backend/pytest.ini`. Nothing errored — suite green on first run.
- [x] Full backend suite: 631 passed in 113s under 5.2.16, settings-reload tests included, zero deprecation errors.
- [x] Admin verified on local under CSP: login + courses changelist render correctly, console shows no CSP violations. Changelist still carries an inline `style` attribute, so `'unsafe-inline'` for style-src is still required; comment updated to say "Django 5.2 admin".
- [x] [P] Stale version references updated: `backend/config/settings.py` CSP comment, `README.md` tech-stack table, `CLAUDE.md` line 6 — all now say Django 5.2.
- [x] Neon prod schema check (2026-07-29): direct `migrate --check` from dev machine was permission-blocked, so equivalent evidence gathered via Neon MCP — all 84 migrations in the local Django 5.2.16 plan (`showmigrations --plan`) are present in prod `django_migrations`; only extras in prod are 4 historical `authtoken` rows from a long-removed app. No unapplied migrations, no schema drift.

## Frontend tasks

None. (`npx tsc --noEmit` and `npm run lint` still run as part of /verify-stack but no frontend file changes.)

## Verification

- `/verify-stack` PASS: full backend suite (631+ tests), `tsc --noEmit` 0 errors, eslint 0 errors. Paste output.
- `docker compose exec backend python -c "import django; print(django.get_version())"` prints `5.2.x`.
- `makemigrations --check --dry-run` clean locally.
- `DATABASE_URL=<neon prod> python manage.py migrate --check` output captured (expected: no unapplied migrations, since deps other than Django are untouched).
- **Migration rehearsal (only if a new migration appears):** create a Neon branch off prod (`mcp neon create_branch` or dashboard), run `migrate` against the branch connection string, run a smoke query (course list, user count), then delete the branch. Only after a clean rehearsal does the user apply to the real prod branch manually. New migrations do NOT block the PR, but prod apply is user-run and happens before or with the deploy, never automated.
- pytest emits zero `RemovedInDjango60Warning` (they are errors now — a green suite is the proof).
- Manual click-through on local: login/logout (JWT via dj-rest-auth), student opens a ROB101 lesson and completes its comprehension check, instructor opens a course outline page, `/admin/` renders with no CSP violations, trigger a password-reset email and check its rendering in the console/Mailpit output.
- CI green on the PR, including the `pip-audit` job and the pre-suite `collectstatic --noinput` step.
- Post-merge (user-run): Render auto-deploys on merge to main; confirm `PYTHON_VERSION=3.12` still set in the Render dashboard beforehand, then check `https://api.stemquests.com/api/health/` and a login on stemquests.com after deploy.

## Notes for the implementer

- Render uses the native Python runtime — `pip install -r requirements.txt` at build. The deploy never runs `migrate`; any prod migration is applied manually from a dev machine.
- `pyjwt==2.13.0` is pinned above an advisory floor — do not let resolution drift it.
- Backend changes need `docker compose restart backend`; a requirements change needs a rebuild.
