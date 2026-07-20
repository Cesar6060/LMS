# Handoff: Phase 36 — GitHub Actions CI

## Current state
Phase 36 **implemented + verified**, PR #21 open against `lms/main`
(https://github.com/Cesar6060/LMS/pull/21). Branch
`feat/phase-36-github-actions-ci`, cut from fresh `lms/main` @ `e02b893`
(after Phase 35's PR #20 merged). Commits: `9f7cc9f` (workflow + badge +
specs), `6a82c1c`/`37a130d` (deliberate CI-gate failure + revert), `92b37cc`
(spec checklist).

- `.github/workflows/ci.yml` (new) — `pull_request` (all branches) +
  `push: [main]`; `concurrency: ci-${{ github.ref }}`, `cancel-in-progress`.
  - **backend**: `postgres:16-alpine` service (`gamedev_db`/`gamedev_user`/
    `devpassword` = the `settings.py` defaults) + `pg_isready` health check;
    `checkout@v4`, `setup-python@v5` (3.12, pip cache on
    `backend/requirements.txt`); `pip install -r requirements.txt` then
    `pytest` in `backend`, only `DB_HOST=localhost` set.
  - **frontend**: `setup-node@v4` (22, npm cache on `package-lock.json`);
    `npm ci` → `npx tsc --noEmit` → `npm run lint` → `npm run build`, all in
    `frontend`. `VITE_API_URL` deliberately unset.
- `README.md` — CI status badge under the title.
- `docs/specs/deployment-overview.md` + `phase-36-github-actions-ci.md` (were
  untracked; now committed). **No source changes** in `backend/`/`frontend/`.

Verified locally: **pytest 346 passed**, **tsc 0 errors**, **lint 0 errors /
22 warnings** (= baseline), plus `npm run build` ✓ 2.87s. Verified in CI on
PR #21: backend pass 2m29s / frontend pass 36s; gate proven with a temp
failing assert (backend **fail** — `assert 8 == 9`, 1 failed / 345 passed;
frontend still pass); after revert both **pass** (2m24s / 38s).

## In progress / not done
- **PR #21 not merged** — the last spec checklist item (merge → green
  `push`-to-`main` run → badge shows passing). Left to the user per the
  review-then-merge pattern of prior phases.

## Next steps
1. Review + merge PR #21 (`feat/phase-36-github-actions-ci` → `lms/main`).
2. Confirm the `push`-to-`main` run is green and the badge renders passing;
   check off the final item in `docs/specs/phase-36-github-actions-ci.md`.
3. Delete merged local branches: `feat/phase-34-student-dashboard`,
   `feat/phase-35-course-map`, `feat/phase-36-github-actions-ci`.
4. Start **Phase 37 — backend production readiness (code only)**: write
   `docs/specs/phase-37-*.md` first (workflow rule), scope from row 37 of the
   deployment overview. Its explicit constraint: the prod `VITE_API_URL` guard
   must throw at **runtime**, not build time, or CI's frontend build breaks.

## Decisions made
- Postgres service env mirrors the `settings.py` defaults so the workflow only
  overrides `DB_HOST` — fewer moving parts than restating every `DB_*`.
- Kept `npm run build` despite it re-running `tsc -b`: early tripwire for the
  exact bundle Cloudflare Pages runs in Phase 39 (spec's rationale).
- Two throwaway commits for the gate check rather than a scratch branch, so the
  evidence lives on the PR; reverted via `git revert` (history keeps the proof).

## Gotchas discovered
- The `backend` job runs ~2m25s vs the frontend's ~35s (pip install of
  `psycopg[binary]`/pillow/sentry dominates). Don't expect fast PR feedback.
- After a push, `gh pr checks 21` briefly says "no checks reported" before the
  new run registers — wait, don't read it as a failure.
- No local YAML linter: no `pyyaml` in the backend image, none on the host.
  Validated via `docker compose exec -T frontend sh -c 'cat > /tmp/ci.yml &&
  npx --yes js-yaml /tmp/ci.yml'` < the file.
- zsh still shadows `head` (use `/usr/bin/head`).

## Files to read first
- `docs/specs/deployment-overview.md` — 36–40 roadmap + shared decisions
- `docs/specs/phase-36-github-actions-ci.md` — only the merge item open
- `.github/workflows/ci.yml`
- `backend/config/settings.py` — `DATABASES` block (~lines 83–92)
