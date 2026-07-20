# Phase 36 — GitHub Actions CI

Part of the deployment track — read `docs/specs/deployment-overview.md` for
the full 36–40 roadmap and shared decisions.

## Goal

Stand up the repo's first CI: a GitHub Actions workflow on `Cesar6060/LMS`
that runs the backend test suite against a real Postgres 16 and the frontend
type check, lint, and production build, on every pull request and every push
to `main`. This is the quality gate every later deployment phase (37–40)
merges behind, and the frontend build job is an early tripwire for the exact
build Cloudflare Pages will run in Phase 39. No deployment work in this
phase — code and workflow files only.

## Out of scope

- Any deploy automation (Render/Pages hookup is Phases 38–39)
- Deploy gating on CI status / branch protection rules (optional follow-up;
  merge discipline is the gate per the overview)
- Coverage reporting/thresholds (pytest-cov is installed; wiring reports up
  is a later nicety)
- Backend Docker image builds in CI (Render uses native Python runtime)
- Caching Docker layers, matrix builds, scheduled runs
- Fixing any pre-existing lint warnings (baseline is 0 errors / 22 warnings —
  the lint job must pass at that baseline, i.e. errors fail, warnings don't)

## Preconditions

- Phase 35 PR #20 (`feat/phase-35-course-map` → `lms/main`) reviewed and
  merged; branch this phase from fresh `lms/main` (suggested:
  `feat/phase-36-github-actions-ci`).
- GitHub Actions enabled on `Cesar6060/LMS` (default-on for personal repos —
  just confirm under Settings → Actions that workflows are allowed).

## Backend tasks

- [x] None in `backend/` source. The suite must pass as-is in CI; if a test
      turns out to depend on docker-compose specifics (it shouldn't — tests
      read the same `DB_*` env vars settings already use), fix the test, not
      the workflow.

## Workflow tasks (`.github/workflows/ci.yml`)

- [x] Triggers: `pull_request` (all branches) and `push` to `main`.
- [x] `concurrency` group per ref with `cancel-in-progress: true` (don't
      stack runs on rapid pushes).
- [x] **Job `backend`** (ubuntu-latest):
  - [x] `services: postgres` → `postgres:16-alpine` with env
        `POSTGRES_DB=gamedev_db`, `POSTGRES_USER=gamedev_user`,
        `POSTGRES_PASSWORD=devpassword` (matches the defaults in
        `backend/config/settings.py`), port 5432 mapped, health-check options
        (`pg_isready` interval/retries) so steps wait for readiness.
  - [x] `actions/checkout@v4`, `actions/setup-python@v5` with Python 3.12
        and built-in pip cache keyed on `backend/requirements.txt`.
  - [x] `pip install -r requirements.txt` then `pytest` with
        `working-directory: backend` and env `DB_HOST=localhost`
        (name/user/password/port fall through to settings defaults;
        pytest-django creates/destroys its own `test_gamedev_db`).
- [x] **Job `frontend`** (ubuntu-latest, independent of backend):
  - [x] `actions/checkout@v4`, `actions/setup-node@v4` with Node 22 and npm
        cache keyed on `frontend/package-lock.json`.
  - [x] `npm ci`, then `npx tsc --noEmit`, then `npm run lint`, then
        `npm run build` — all with `working-directory: frontend`. The build
        step is deliberate duplication of tsc (build runs `tsc -b`): it
        proves the Vite production bundle compiles before Pages ever runs it.
        `VITE_API_URL` is intentionally unset here — the current localhost
        fallback makes the build succeed; Phase 37/39's prod guard must be
        written to throw at **runtime** in prod, not at build time, so CI
        builds keep working without the var.
- [x] README: add the Actions status badge for the workflow near the top.

## Frontend tasks

- [x] None in `frontend/` source (lint/tsc/build must already pass — they do
      per the Phase 35 handoff baseline).

## Verification

- [x] Local `/verify-stack` still green before pushing (pytest 346, tsc 0
      errors, lint 0 errors / 22 warnings).
- [ ] Push the branch, open a PR against `lms/main`: both `backend` and
      `frontend` jobs run and pass on the PR.
- [ ] Sanity-check the gate actually gates: push a temporary commit with a
      deliberately failing assert in `backend/courses/tests.py` → backend job
      goes red on the PR; revert the commit → green again. (Two throwaway
      commits on the PR branch; revert before merge.)
- [ ] Merge the PR: the `push`-to-`main` run also passes and the README
      badge shows passing.
