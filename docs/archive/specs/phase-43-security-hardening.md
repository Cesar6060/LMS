# Phase 43: Security Hardening — Tokens, Storage, Headers

## Goal

Close the three structural security gaps that phase 42 deferred or didn't
reach: (1) replace non-expiring DRF tokens with short-lived JWTs
(dj-rest-auth `USE_JWT` + simplejwt) so a leaked token stops working on its
own; (2) make lesson-attachment/avatar files private on R2 and hand out
expiring signed URLs, so a shared attachment link can no longer bypass the
enrollment checks the API enforces; (3) add the cheap hardening the audit
flagged — CSP and Permissions-Policy headers, HSTS preload, and a size cap
on lesson-attachment uploads (avatars are capped; attachments aren't).
The app remains a locked public demo (registration off, shared
`jdoe@demo.com` login), so all changes must keep that flow working.

## Out of scope

- Real SMTP email (password resets keep printing to Render logs) — deferred
  again; registration is off so resets are moot.
- httpOnly-cookie JWT transport (tokens stay in localStorage; CSRF-free
  Bearer flow). Revisit if the app ever leaves demo mode.
- Celery/queue for announcement emails (still fire-and-forget thread).
- `ACCOUNT_EMAIL_VERIFICATION` changes — moot while registration is off.
- Re-enabling registration in any form.
- Instructor-approval step for enrollments. Considered and deliberately
  skipped: registration is fully disabled and joining a course already
  requires a per-course `enrollment_code` (instructor-visible,
  regenerable — `courses/views.py` `enroll` action), so strangers are
  double-gated. **Revisit whenever registration reopens**: add a
  `pending` enrollment status + instructor accept/decline UI in that
  same phase.

## Context from recon (file references)

- Auth: `backend/config/settings.py` — `REST_FRAMEWORK` (~line 194,
  `TokenAuthentication` + `SessionAuthentication`), `REST_AUTH` (~line 292,
  `USE_JWT: False`, stock `authtoken.Token`). Frontend:
  `frontend/src/services/api.ts` (interceptors, `Authorization: Token …`),
  `frontend/src/services/auth.ts` (stores `response.data.key` in
  localStorage), `frontend/src/contexts/AuthContext.tsx`.
- Storage: `settings.py` `USE_R2` block (~line 164) — `querystring_auth:
  False`, `default_acl: None`, `custom_domain: R2_PUBLIC_HOST` → public
  permanent URLs. Serializers build URLs at
  `backend/courses/serializers.py:20-22` and
  `backend/accounts/serializers.py:24-26`.
- Uploads: avatar cap in `backend/accounts/views.py:78`
  (`AVATAR_MAX_UPLOAD_BYTES`); **no** cap on `LessonAttachment`
  (`backend/courses/models.py:468`).
- Headers: `USE_HTTPS` block (~line 226) has HSTS/nosniff/referrer but no
  CSP, no Permissions-Policy, no `SECURE_HSTS_PRELOAD`.

## Backend tasks

### JWT migration
- [x] Add `djangorestframework-simplejwt` (pinned) to
      `backend/requirements.txt`; `docker compose build backend`.
- [x] `settings.py`: add `rest_framework_simplejwt.token_blacklist` to
      `INSTALLED_APPS`; remove `rest_framework.authtoken`. Run/commit the
      blacklist migrations (`python manage.py migrate` — new tables only;
      run `db-migration-checker` agent on them).
- [x] `settings.py` `REST_AUTH`: `USE_JWT: True`,
      `JWT_AUTH_HTTPONLY: False` (refresh token returned in the response
      body), remove `TOKEN_MODEL` (set `None`).
- [x] `settings.py` `SIMPLE_JWT`: `ACCESS_TOKEN_LIFETIME` 60 min,
      `REFRESH_TOKEN_LIFETIME` 7 days, `ROTATE_REFRESH_TOKENS: True`,
      `BLACKLIST_AFTER_ROTATION: True`.
- [x] `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES`: replace
      `TokenAuthentication` with `dj_rest_auth.jwt_auth.JWTCookieAuthentication`
      (works for pure-header mode too); keep `SessionAuthentication` (admin).
- [x] Confirm `/api/auth/token/refresh/` (or dj-rest-auth's
      `token/refresh/` route) is mounted in `backend/accounts/urls.py`;
      verify logout blacklists the refresh token.
- [x] Review `backend/accounts/serializers.py` custom serializers — nothing
      may reference the old Token model; login response is now
      `{access, refresh, user}` not `{key}`.
- [x] Tests: login returns `access`+`refresh` and no `key`; authenticated
      request with `Bearer` works while `Token <old>` is rejected; refresh
      endpoint issues a new pair; logout blacklists (refresh reuse → 401);
      expired access token → 401 (override lifetime in test).

### Private R2 + signed URLs
- [x] `settings.py` `USE_R2` block: `querystring_auth: True`, drop
      `custom_domain`, add `url_expire` from new env
      `R2_SIGNED_URL_TTL` (default 3600 s). Keep `default_acl: None`,
      `file_overwrite: False`.
- [x] Update `backend/config/tests/test_storage_settings.py` for the new
      values; add a test that generated URLs contain an expiry/signature
      param when `USE_R2` is on.
- [x] `render.yaml`: add `R2_SIGNED_URL_TTL` (committed, `3600`);
      `R2_PUBLIC_HOST` becomes unused — remove it from `render.yaml` and
      `.env.example`.
- [x] Verify serializer URL paths still work: with signed storage,
      `obj.file.url` is already absolute — `build_absolute_uri` must not
      mangle it (it doesn't for absolute URLs, but assert in a test).

### Upload cap + headers
- [x] New setting `ATTACHMENT_MAX_UPLOAD_BYTES` (default 25 MB), enforced
      in the lesson-attachment upload view in `backend/courses/views.py`
      before storage, mirroring the avatar pattern
      (`backend/accounts/views.py:78-92`). Test: oversized upload → 400.
- [x] Add `django-csp` (pinned); strict policy for the API/admin host
      (`default-src 'none'` for API responses; relax only what the Django
      admin needs, e.g. `'self'` + inline styles for admin pages).
- [x] Permissions-Policy header (e.g. `django-permissions-policy` or a
      one-line middleware): deny `camera`, `microphone`, `geolocation`.
- [x] `SECURE_HSTS_PRELOAD = True` inside the `USE_HTTPS` block.
- [x] Extend `backend/config/tests/test_production_settings.py` to assert
      CSP/Permissions-Policy/preload appear under prod-like settings.

## Frontend tasks

- [x] `frontend/src/services/auth.ts`: store `response.data.access` and
      `response.data.refresh` (keys `token`/`refresh` in localStorage);
      logout POSTs the refresh token then clears both in `finally`.
- [x] `frontend/src/services/api.ts`: request interceptor sends
      `Authorization: Bearer ${token}`. Response interceptor: on 401, try
      one silent refresh (`POST /auth/token/refresh/` with the stored
      refresh token), replay the original request; queue concurrent 401s
      behind a single in-flight refresh; on refresh failure, clear both
      tokens and redirect to `/login?next=…` (existing behavior).
- [x] `frontend/src/types/` auth types: login response `{access, refresh,
      user}`; drop `key`.
- [x] `frontend/src/contexts/AuthContext.tsx`: no structural change
      expected — verify `refreshUser` failure path clears both tokens.
- [x] Add `frontend/public/_headers` (Cloudflare) setting CSP for the app
      host (`default-src 'self'`; `img-src 'self' https://*.r2.cloudflarestorage.com data:`;
      `connect-src 'self' https://stemquest-api.onrender.com`; adjust to
      actual hosts), plus `Permissions-Policy` and
      `X-Content-Type-Options: nosniff`. If the frontend deploy isn't
      Cloudflare Pages (check phase 39 handoff/deploy docs), do the
      equivalent in that host's header config instead.
- [x] `npx tsc --noEmit` 0 errors; `npm run lint` no new warnings over the
      22-warning baseline.

## Operator steps (Cesar, at deploy — not code)

1. Cloudflare dashboard: disable the R2 bucket's public `pub-*.r2.dev`
   access (bucket → Settings → Public access). Do this only when PR merges
   — flipping early breaks attachments on the current deploy.
2. Render dashboard: delete the now-unused `R2_PUBLIC_HOST` env var.
3. Expect every existing session to be logged out on deploy (token scheme
   changed) — demo users just log in again.

## Verification

- [x] `/verify-stack` PASS (backend pytest in Docker, tsc, lint) — show
      output.
- [x] Specific pytest cases pass: JWT login/refresh/logout-blacklist/expiry
      set above; signed-URL storage tests; oversized attachment 400; header
      assertions in `test_production_settings.py`.
- [x] Phase 42 regressions still green: `POST /api/auth/registration/` →
      403; `PATCH /api/auth/profile/ {"is_instructor": true}` → stays
      false; demo password change blocked.
- [x] Manual flow (local, `USE_R2` off): log in as demo student → browse
      JAVA101 → download a lesson attachment → log out → confirm the API
      rejects the old access token after logout+expiry.
- [x] Manual flow (after prod deploy) — verified 2026-07-22 during phase
      46: live media URL contains `X-Amz-Signature`/`X-Amz-Expires` and
      serves 200; the same URL with the signature stripped → 400 (no
      lesson attachments exist in prod, so this was exercised via an
      avatar upload+delete on the demo account); login/refresh works on
      the live site; `/api/health/?deep=1` → ok. Remaining sub-item —
      direct `pub-*.r2.dev` access erroring — lands with the Cloudflare
      lockdown flip, tracked as phase 46 runbook step 5.
