# Phase 39 — Frontend on Cloudflare Pages + media on R2

## Goal

Put the React frontend live on Cloudflare Pages and move uploaded media
(avatars, lesson attachments) to Cloudflare R2, completing the user-facing
production deployment started in Phases 36–38. After this phase, a student
can register, enroll, and work through JAVA101 entirely at the
`https://<project>.pages.dev` URL against the live Render API
(`https://stemquest-api.onrender.com`), with avatars and attachments
uploaded to and served from a public R2 bucket (`pub-<hash>.r2.dev`) —
fixing the known Phase 38 gap where media 404s on Render's ephemeral disk.
All new backend behavior is gated on `USE_R2` so local docker-compose dev
is untouched.

## Scoping decisions (interview, 2026-07-20)

- **Preview deployments**: CORS stays prod-Pages-URL-only. Pages preview
  builds will render but their API calls fail CORS — accepted; revisit if
  previews become part of the workflow.
- **`VITE_API_URL` guard fails the build** (vite.config throws when
  `mode === 'production'` and the var is unset), so a misconfigured Pages
  project fails loudly instead of shipping a site pointed at localhost.
  CI gets a dummy `VITE_API_URL` (its current comment says the localhost
  fallback is load-bearing — that changes).
- **Tests**: settings-gate test for the storage swap **plus** API tests for
  avatar upload/delete and attachment upload/delete (currently zero
  coverage on endpoints that become load-bearing this phase).
- **Frontend Sentry deferred**: `VITE_SENTRY_DSN` stays unset; decide with
  Phase 40 observability.

## Out of scope

- Custom domain / DNS (roadmap decision, deferred)
- Real email provider (Render free tier blocks SMTP anyway)
- Preview-deployment CORS support (see above)
- Frontend Sentry / `VITE_SENTRY_DSN` (see above)
- Private media, presigned URLs, or auth-enforced downloads (public-read
  r2.dev accepted per deployment overview)
- Migrating existing media: prod has none worth keeping (the two Phase 38
  click-through uploads already 404), local dev media stays local
- R2 in local dev — docker-compose keeps `FileSystemStorage`
- Observability (Phase 40); Redis/Channels; staging environment
- Removing the unused-but-declared `VITE_WS_URL` typing (noise, not harm)

## Backend tasks

- [x] `backend/requirements.txt`: add `django-storages[s3]==1.14.6`
      (pulls boto3; pin follows the existing everything-pinned style).
- [x] `backend/config/settings.py`: gated R2 block after the existing
      `STORAGES` dict (`settings.py:144-155`), mirroring the `USE_HTTPS`
      opt-in idiom (`settings.py:191-207`):

      ```python
      USE_R2 = config('USE_R2', default=False, cast=bool)
      if USE_R2:
          STORAGES['default'] = {
              'BACKEND': 'storages.backends.s3.S3Storage',
              'OPTIONS': {
                  'access_key': config('R2_ACCESS_KEY_ID'),
                  'secret_key': config('R2_SECRET_ACCESS_KEY'),
                  'bucket_name': config('R2_BUCKET_NAME'),
                  'endpoint_url': f"https://{config('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
                  'custom_domain': config('R2_PUBLIC_HOST'),  # pub-<hash>.r2.dev
                  'querystring_auth': False,
                  'default_acl': None,
                  'file_overwrite': False,
                  'region_name': 'auto',
                  'signature_version': 's3v4',
              },
          }
      ```

      Notes: missing `R2_*` vars under `USE_R2=true` fail fast via
      decouple's `UndefinedValueError` (matches the existing
      `ImproperlyConfigured` guard philosophy at `settings.py:26-34`).
      With `custom_domain` set, `.url` returns
      `https://pub-<hash>.r2.dev/<upload_to path>`;
      `request.build_absolute_uri()` in the two serializers
      (`accounts/serializers.py:19-25`, `courses/serializers.py:10-22`)
      passes absolute URLs through unchanged — no serializer changes.
- [x] `render.yaml`: add `USE_R2` (`value: "true"`) and `sync: false`
      entries for `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
      `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_PUBLIC_HOST`.
- [x] `backend/.env.example`: document `USE_R2` + the five `R2_*` vars
      (commented out, defaults off). *Deviation: the file lives at the
      repo root (`.env.example`), not `backend/` — updated there.*
- [x] Settings tests (extend `config/tests/test_production_settings.py`
      or a new `config/tests/test_storage_settings.py`, following that
      file's env-override/reload pattern):
      - [x] default env → `STORAGES['default']['BACKEND']` is
            `FileSystemStorage`
      - [x] `USE_R2=true` + all `R2_*` set → backend is
            `storages.backends.s3.S3Storage` with
            `querystring_auth=False`, `default_acl=None`,
            `custom_domain` = the env value
      - [x] `USE_R2=true` with a missing `R2_*` var → raises (fail-fast)
- [x] Upload endpoint tests, run against temp-dir `FileSystemStorage`
      (`override_settings(MEDIA_ROOT=tmp_path)`), no R2 mocking:
      - [x] `accounts/tests.py`: avatar upload (multipart, tiny real PNG
            bytes — it's an `ImageField`) → 200 and `avatar_url` absolute;
            replace deletes old file; delete avatar → `avatar_url` null;
            unauthenticated → 401
      - [x] `courses/tests.py`: attachment upload as instructor → 201 and
            serializer `url` absolute; upload as student → 403; delete
            removes the stored file; 10-per-lesson limit still enforced

## Frontend tasks

- [x] `frontend/public/_redirects` (new file):
      `/*    /index.html   200` — SPA fallback for BrowserRouter
      deep-link refreshes (`src/main.tsx:35`).
      *2026-07-21 pivot: Cloudflare retired the Pages git-connect flow
      for new projects, so the frontend deploys as a Workers
      static-assets site instead. `_redirects` removed; replaced by
      `frontend/wrangler.jsonc` with
      `assets.not_found_handling = "single-page-application"`.*
- [x] `frontend/vite.config.ts`: production guard —
      `defineConfig(({ mode }) => ...)` with
      `loadEnv(mode, process.cwd(), '')`; throw a clear error when
      `mode === 'production'` and `VITE_API_URL` is unset. (Use `loadEnv`,
      not `import.meta.env`, which doesn't exist in the config file; Pages
      supplies the var via process env, which `loadEnv('')` includes.)
- [x] `frontend/src/services/api.ts`: export the resolved `API_URL`;
      `frontend/src/services/courses.ts:365` imports it instead of
      duplicating the `import.meta.env.VITE_API_URL || localhost` fallback
      (`getGradebookExportUrl` keeps building the raw URL — it just stops
      having its own copy of the base).
- [x] `.github/workflows/ci.yml:95-101`: set `VITE_API_URL` on the
      "Production build" step (e.g.
      `env: { VITE_API_URL: "http://localhost:8000/api" }`) and rewrite
      the now-wrong comment — the guard makes an unset var a build error
      by design.

## Infra tasks (dashboards; secrets never in repo or chat)

- [ ] **R2**: create bucket (suggest `stemquest-media`), enable the public
      `r2.dev` dev subdomain (note the `pub-<hash>.r2.dev` host), create
      an API token scoped to Object Read & Write on that bucket only →
      access key ID + secret. Bucket-side CORS: none needed (media is
      consumed via `<img src>`/`<a href>`, not fetch/XHR).
- [ ] **Render**: set the six new env vars; update
      `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, and `FRONTEND_URL`
      from `localhost:5173` to the Pages URL. Formatting traps from the
      Phase 38 gotcha apply: exact scheme, no trailing slash, and env-var
      saves auto-redeploy (~2 min stale window).
- [ ] **Cloudflare Pages**: create project from `Cesar6060/LMS`,
      production branch `main`, root dir `frontend`, build command
      `npm run build`, output dir `dist`, `NODE_VERSION=22`,
      `VITE_API_URL=https://stemquest-api.onrender.com/api`
      (**must include the `/api` suffix** — the axios client appends
      nothing).
      *2026-07-21 pivot: Pages git-connect retired → Workers Builds
      instead. Project name `stemquest`, path `frontend`, build
      `npm run build`, deploy `npx wrangler deploy`, same two env vars
      as build variables; site URL becomes
      `https://stemquest.<subdomain>.workers.dev`. See runbook step 4.*
- [x] Write the deploy runbook as **plain text** (user preference):
      `docs/runbooks/phase-39-deploy-steps.txt`, in as-actually-run order.

## Verification

- [x] `/verify-stack` PASS: pytest (354 baseline + new tests, 0 failures),
      `tsc --noEmit` 0 errors, lint 0 errors / ≤22 warnings (baseline).
      *2026-07-20: pytest 372 passed (18 new), tsc 0, lint 0/22.*
- [x] Guard proof, locally: `npm run build` with `VITE_API_URL` unset
      **fails** with the clear error; with it set, succeeds.
      *2026-07-20: both proven; `dist/_redirects` confirmed in output.*
- [x] CI green on the PR (confirms the ci.yml env addition works).
      *2026-07-20: PR #26 head `33dd781` — Backend (pytest) 2m47s,
      Frontend (tsc, lint, build) 38s, both pass.*
- [x] `curl -I https://<project>.pages.dev/` → 200; a deep link like
      `/courses` fetched directly → 200 serving `index.html`
      (`_redirects` working).
- [x] `curl -H "Origin: https://<project>.pages.dev" -I
      https://stemquest-api.onrender.com/api/health/` →
      `access-control-allow-origin` header present.
- [x] After an avatar upload: the object is visible in the R2 bucket, and
      its URL is `https://pub-<hash>.r2.dev/avatars/...` serving 200 with
      an image content-type.
      *2026-07-21: all verified against the live stack — site is
      `https://stemquest.cesarvillarreal11.workers.dev` (workers.dev,
      not pages.dev, per the Workers pivot); avatar upload → 200 →
      `pub-28b0ff93….r2.dev/avatars/…` served 200 `image/png` →
      delete → 404. See runbook AS-RUN NOTES.*
- [ ] **Full prod click-through** (per deployment overview "done when"):
      register a new student, enroll in JAVA101, open the course map,
      **hard-refresh a deep link**, upload an avatar (renders from
      `r2.dev` in header + settings), instructor uploads a lesson
      attachment, student downloads it, gradebook CSV export link works —
      **zero CORS or mixed-content errors in the console** throughout.
- [ ] Opportunistic (deferred from Phase 38): record one cold-start
      timing figure for the Render free tier.

## Keys/credentials needed (user-provided, dashboards only)

- R2 access key ID + secret (bucket-scoped token), Cloudflare account ID,
  bucket name, `pub-<hash>.r2.dev` host
- Nothing else — `VITE_SENTRY_DSN` deferred
