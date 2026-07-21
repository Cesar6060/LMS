# Handoff: Phase 39 — Frontend on Cloudflare Pages + media on R2 (code side)

## Current state

**All code for Phase 39 is done, verified, and up as PR #26**
(`feat/phase-39-frontend-pages-media-r2` → `main` on `Cesar6060/LMS`,
commit `1816396`). What remains is dashboard-only work (R2 bucket, Render
env vars, Cloudflare Pages project) — it needs Cesar's accounts and is
laid out step-by-step in `docs/runbooks/phase-39-deploy-steps.txt` and
summarized in the untracked repo-root `PHASE-39-USER-ACTIONS.txt`.

What the code does:

- `backend/config/settings.py`: `USE_R2`-gated swap of
  `STORAGES['default']` to `storages.backends.s3.S3Storage` pointed at
  R2 (`custom_domain` = the public `pub-<hash>.r2.dev` host, so `.url`
  is already absolute; `querystring_auth=False`, `default_acl=None`,
  `file_overwrite=False`). Mirrors the `USE_HTTPS` idiom: inert unless
  set, and a missing `R2_*` var under `USE_R2=true` raises decouple's
  `UndefinedValueError` at boot (fail-fast, deliberate).
- `backend/requirements.txt`: `django-storages[s3]==1.14.6` (brings
  boto3 1.43.52). Backend Docker image rebuilt locally with it.
- `render.yaml`: `USE_R2="true"` + five `sync: false` `R2_*` vars;
  parses clean via js-yaml (18 envVars total).
- Frontend: `public/_redirects` (`/* /index.html 200`);
  `vite.config.ts` now uses the function form + `loadEnv` and **throws
  on production builds without `VITE_API_URL`**; `api.ts` exports
  `API_URL` and `courses.ts:getGradebookExportUrl` reuses it; CI's
  "Production build" step supplies a dummy `VITE_API_URL` (comment
  rewritten — the old one said the localhost fallback was load-bearing).

## Verification evidence

- `/verify-stack` PASS: pytest **372 passed** (354 baseline + 18 new:
  8 storage-settings, 5 avatar, 5 attachment), tsc **0 errors**, lint
  **0 errors / 22 warnings** (= baseline).
- Guard proven locally both ways: `npm run build` without
  `VITE_API_URL` fails with the clear error; with it set, builds in
  ~2.3 s and `dist/_redirects` is present in the output.
- New tests all run against temp-dir `FileSystemStorage`
  (`settings.MEDIA_ROOT = tmp_path` via autouse fixture) — no R2
  mocking anywhere. The R2 swap itself is covered by
  `config/tests/test_storage_settings.py`, which reloads
  `config.settings` under a patched environment (the reload fixture
  calls `monkeypatch.undo()` *before* its own restore-reload — fixture
  teardown ordering matters there).

## Deviations from the spec

- `.env.example` lives at the **repo root**, not `backend/` — the R2
  block was documented there (spec annotated).
- Nothing else; every code checklist item is ticked in
  `docs/specs/phase-39-frontend-pages-media-r2.md`.

## In progress / not done

- **PR #26 not merged** (user's call, as always). CI was still running
  at handoff time — check `gh pr checks 26 --repo Cesar6060/LMS`.
- **All infra steps** (runbook steps 1–6): R2 bucket + token, Render
  R2_* env vars, Pages project, CORS/CSRF/FRONTEND_URL swing to the
  Pages URL, curl verification, full prod click-through, cold-start
  timing figure (deferred from Phase 38 again).
- **Merge-order trap, flagged in the runbook**: merging the PR makes
  Render redeploy with `USE_R2="true"` before the `R2_*` secrets exist
  in the dashboard → the service fails at boot **by design** until
  they're saved. Either enter the secrets first or accept one red
  deploy.

## Gotchas discovered

- Host `frontend/node_modules` had only **linux** rollup binaries (the
  lockfile was generated inside the Linux container + npm optional-deps
  bug npm/cli#4828). Fixed with
  `npm install --no-save @rollup/rollup-darwin-arm64` — `--no-save` so
  the lockfile (which CI's `npm ci` uses) stays untouched. If host
  builds break again with "Cannot find module @rollup/rollup-darwin-arm64",
  rerun that.
- `frontend/node_modules` on the host **cannot be rm -rf'd** — the
  directory itself is a Docker Desktop mount point (anonymous volume
  over the bind mount); contents delete, the dir returns
  "Permission denied". Install into it instead of removing it.
- `user.preferences` in accounts tests is a **stale cached relation**:
  a signal creates the row at user creation and caches the empty
  instance on the fixture's user object, so the avatar the view saves
  is invisible through it. Query
  `UserPreferences.objects.get(user=user)` fresh instead.
- The running frontend container's `node_modules` volume is still the
  stale pre-recharts one (Phase 38 gotcha) — `npm run build` inside it
  fails on `@dnd-kit`/`recharts` imports. Host builds are the reliable
  path for build proofs.
- `frontend/tsconfig.tsbuildinfo` is tracked and churns on every local
  build — `git checkout --` it before committing.

## Next steps

1. Cesar: work through `PHASE-39-USER-ACTIONS.txt` (merge PR #26, R2
   bucket + token, Render env vars, Pages project, origin swing).
2. Claude (once the Pages URL exists): curl verification block in
   runbook step 6, then support the click-through; record one
   cold-start figure.
3. Phase 40: observability (decide frontend Sentry / `VITE_SENTRY_DSN`
   there).

## Files to read first

- `docs/specs/phase-39-frontend-pages-media-r2.md` — checklist, code
  items all ticked
- `docs/runbooks/phase-39-deploy-steps.txt` — the deploy, in run order
- `PHASE-39-USER-ACTIONS.txt` (repo root, untracked) — Cesar's short list
