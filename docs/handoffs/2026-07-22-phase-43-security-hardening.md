# Handoff: Phase 43 — JWT auth, private R2 signed URLs, security headers

## Current state
Phase 43 code DONE on branch `feat/phase-43-security-hardening`, PR
https://github.com/Cesar6060/LMS/pull/34 open against LMS main (phase 42 #33
merged). Three deliverables: (1) DRF tokens → simplejwt JWTs (60 min access /
7 day refresh, `ROTATE_REFRESH_TOKENS` + blacklist on rotation and logout;
frontend does Bearer auth with a silent single-flight refresh on 401);
(2) R2 media private — `querystring_auth: True` + `querystring_expire` from
`R2_SIGNED_URL_TTL` (3600), `custom_domain`/`R2_PUBLIC_HOST` retired;
(3) strict CSP (django-csp 4.0) + Permissions-Policy on the API host,
`frontend/public/_headers` CSP for the Workers app host, HSTS preload,
`ATTACHMENT_MAX_UPLOAD_BYTES` (25 MB) replacing a hardcoded 10 MB cap.
Modified: `backend/config/{settings,middleware(new)}.py`,
`backend/config/tests/{test_storage_settings,test_production_settings}.py`,
`backend/accounts/tests.py`, `backend/courses/{views,tests}.py`,
`backend/requirements.txt` (+simplejwt 5.5.0, +django-csp 4.0),
`frontend/src/{types/index.ts,services/{api,auth,courses}.ts,
contexts/AuthContext.tsx,pages/instructor/GradebookPage.tsx}`,
`frontend/public/_headers` (new), `render.yaml`, `.env.example`.
verify-stack PASS: backend **409 passed** (Docker; was 395), tsc 0 errors,
lint 0 errors / 22 warnings (baseline).

## In progress / not done
Nothing half-finished in code. Rollout is blocked on the deploy sequence in
PR #34 — ORDER MATTERS:
1. **Before merge**: apply the third-party simplejwt `token_blacklist`
   migrations to Neon from a dev machine
   (`DATABASE_URL=<neon> python manage.py migrate`). db-migration-checker:
   purely additive/reversible; but new code without these tables 500s on
   every login, so migrate FIRST. Old `authtoken_token` table is orphaned in
   place, not dropped.
2. **Render dashboard**: delete the now-unused `R2_PUBLIC_HOST` env var.
3. Merge PR #34 (auto-deploys Render + Cloudflare Workers).
4. **After deploy**: Cloudflare → R2 bucket → Settings → disable public
   `pub-*.r2.dev` access (early flip breaks attachments on the old deploy).
5. Post-deploy manual checks (last unticked spec item): attachment URL has
   `X-Amz-Signature`/`X-Amz-Expires` and dies after TTL; old `pub-*.r2.dev`
   URL errors; login/refresh works on the live site; `/api/health/?deep=1`
   ok. All sessions are logged out on deploy (expected — token scheme change).

## Decisions made
- `JWT_AUTH_HTTPONLY: False` — tokens stay in localStorage (CSRF-free Bearer
  flow); httpOnly-cookie transport explicitly out of scope while in demo mode.
- Spec's `url_expire` storage option doesn't exist in django-storages 1.14.6 —
  the real option is `querystring_expire` (boot-time ImproperlyConfigured
  caught it). Spec intent preserved.
- Spec recon said lesson attachments had no size cap; there was actually a
  hardcoded 10 MB per-file check. Replaced with the
  `ATTACHMENT_MAX_UPLOAD_BYTES` setting (spec default 25 MB).
- Permissions-Policy via a tiny custom middleware
  (`backend/config/middleware.py`), not django-permissions-policy — one
  static header didn't justify a dependency (spec allowed either).
- CSP/Permissions-Policy are always-on (not USE_HTTPS-gated): API host serves
  only JSON + admin, safe in every env, and tests stay simple.
- Gradebook CSV export moved from raw `fetch` with `Token` header into
  `courseService.exportGradebookCsv` (blob via the api client) so JWT auth +
  silent refresh apply; `API_URL` is no longer exported from api.ts.
- Frontend CSP hosts: YouTube iframe API (`www.youtube.com`, `s.ytimg.com`,
  `i.ytimg.com`), Google Fonts, Sentry ingest, Render API,
  `*.r2.cloudflarestorage.com` for signed media.

## Gotchas discovered
- dj-rest-auth logout under JWT requires the refresh token in the POST body
  (it 401s without one) — the old no-body logout test had to change.
- The refresh endpoint (`/api/auth/token/refresh/`) is auto-mounted by
  dj_rest_auth.urls when USE_JWT is on; response includes
  `access_expiration`/`refresh_expiration` alongside the pair.
- Container entrypoint runs `migrate` on startup, so the blacklist tables
  appeared before the manual `migrate` — "No migrations to apply" is normal.
- Local demo password is `Admin123!` (seed_demo_account), not `Demo123!`.
- Still true: push/PR against remote `lms` (Cesar6060/LMS), `head` is
  shadowed by a curl-like tool in this shell.

## Files to read first
- `docs/specs/phase-43-security-hardening.md` — checklist (all ticked except
  post-deploy manual flow) + out-of-scope list with revisit triggers
- `backend/config/settings.py` — SIMPLE_JWT/REST_AUTH, R2 signed-URL block,
  CONTENT_SECURITY_POLICY
- `frontend/src/services/api.ts` — the 401 → single-flight refresh → replay
  interceptor
- PR #34 body — full deploy sequence with ordering rationale
