# Phase 73 — Security Hardening Audit

## Goal

Audit the platform against a 20-item application security checklist and
remediate the findings in priority order. The audit is complete (findings
below); this phase is the remediation. Fourteen of the twenty items came back
clean and need no work. The remaining findings cluster in four areas: rate
limits that silently default to unlimited when an env var is missing (including
an entirely unthrottled login endpoint), a cross-instructor content exposure
where any `is_instructor` account can read every course's lesson bodies, an
announcement create path with no ownership check, and upload/password/config
hardening. Nothing ships until every Critical and High item is fixed and
verified by a permission-boundary test.

## Audit results — all 20 items

| # | Item | Verdict | Action |
|---|---|---|---|
| 1 | Secrets in repo / git history | **Clean** | Only `.env.example` (placeholders) tracked; `.env` never committed on any branch. Task A7 adds a scanner to CI. |
| 2 | API keys in client bundle | **Clean** | Only `VITE_API_URL` and the public `VITE_SENTRY_DSN`. `SENTRY_AUTH_TOKEN` is build-time only, never in `define`. |
| 3 | Per-tenant isolation at DB layer | **N/A** | Single-tenant LMS; isolation is per-course at the app layer, covered by item 4. |
| 4 | Server-side authorization | **2 findings** | B (cross-instructor content read), C (announcement create). |
| 5 | Rate limiting | **Critical** | A — every scope defaults to unlimited; login unthrottled. |
| 6 | SQL string concatenation | **Clean** | Zero `.raw()` / `.extra()` / `RawSQL`; only raw cursor is a constant `SELECT 1` in `config/health.py:30`. |
| 7 | Input validation | **Clean** | Every serializer uses an explicit `fields` list; DRF validation throughout. |
| 8 | Raw HTML rendering | **Clean** | No `dangerouslySetInnerHTML` anywhere; react-markdown v10 strips raw HTML and `rehype-raw` is absent. Student-authored markdown (discussions) gets GFM only. |
| 9 | Password hashing | **Clean** | Django default PBKDF2-SHA256. No reversible storage. |
| 10 | Tokens in localStorage | **Accepted risk** | Deliberate design — see Accepted Risks. |
| 11 | Unauthenticated admin/debug routes | **1 finding** | F2 — `/api/sentry-debug/` flag is read per-request. Admin itself is staff-gated and path-configurable. |
| 12 | CORS wildcard | **Clean** | Explicit `CORS_ALLOWED_ORIGINS`; `CORS_ALLOW_ALL_ORIGINS` absent from the repo. |
| 13 | Email verification | **Accepted risk** | Deferred on deliverability grounds — see Accepted Risks. |
| 14 | Sequential IDs / IDOR | **Accepted risk** | No bypass found; nested lookups are parent-scoped. See Accepted Risks. |
| 15 | Mass assignment | **Clean** | Zero `fields = '__all__'`; `is_instructor`, XP, streaks, `enrollment_code` all read-only. |
| 16 | Webhook signature verification | **N/A** | No inbound webhook endpoints exist. Resend is outbound SMTP only. |
| 17 | Stack traces / DEBUG in prod | **1 finding** | F1 — `USE_HTTPS` has no boot guard. `DEBUG` already defaults False with a guard. |
| 18 | Dependency CVEs | **1 finding** | G — react-router high-severity advisory. Backend `pip-audit` clean. |
| 19 | Password strength / breach check | **1 finding** | E — no breached-password check. |
| 20 | File upload validation | **1 finding** | D — attachments lack content validation, demo guard, throttle. |

## Out of scope

- Migrating auth tokens to httpOnly cookies (accepted risk, documented below).
- Making email verification mandatory (accepted risk, documented below).
- Converting integer PKs to UUIDs.
- Converting the demo-write guard to default-deny middleware.
- Shortening the R2 presigned-URL TTL.
- The three `_content_upsert` findings and page-scoped `video_position` —
  those are **phase 72**, not this phase.
- Any new product feature. This phase changes security posture only.
- Raising the password minimum length above 8 (decided against: pushes
  school-age students toward reuse; the breach check does the real work).
- MFA / 2FA for staff or instructor accounts.

## Backend tasks

### A. Rate limiting — Critical

The core defect: every scope in `DEFAULT_THROTTLE_RATES`
(`config/settings.py:299-327`) reads an env var with `default=None`, and DRF
treats `None` as unlimited. A missing Render variable silently disables that
limit. `THROTTLE_JOIN_CODE` and `THROTTLE_INVITE_LINK` are unset in production
right now. Separately, `POST /api/auth/login/` has no scoped throttle and
allauth's own `ACCOUNT_RATE_LIMITS` is unconfigured, so there is no
brute-force ceiling on password guessing beyond the (possibly unset) global
`anon` rate.

- [x] **A1.** Replace every `default=None` in `DEFAULT_THROTTLE_RATES` with a
      conservative hardcoded default, so an unset env var means *protected*,
      not unlimited. Use the values `.env.example` already documents as the
      production settings: `anon` 30/min, `user` 120/min, `demo_login` 10/min,
      `password_reset` 5/hour, `invite_send` 30/hour, `invite_accept` 10/hour,
      `invite_link` 60/hour, `join_code` 10/hour, `slide_import` 300/hour. Env
      vars still override. Update the comments — they currently document
      "unset = unlimited" as intended behavior.
- [x] **A2.** ⚠️ **Do A2 in the same commit as A1 or the suite will break.**
      Hardcoded rates apply to the 1181-test suite, where many tests make far
      more than 120 requests/min as one user. Add an autouse fixture in
      `backend/conftest.py` that neutralizes throttle rates for all tests and
      clears the throttle cache between them, with an opt-in marker (e.g.
      `@pytest.mark.throttled`) for the tests that assert throttling. Without
      this, expect widespread spurious 429s.
- [x] **A3.** Add a `login` throttle scope and apply it to the login endpoint.
      **Mount it with `re_path(r'^login/?$', ...)`, not `path()`** — dj-rest-auth
      registers its views with an optional trailing slash, so a `path()` shadow
      captures only `login/` and `/api/auth/login` (no slash) falls through to
      the unguarded original. This exact bug is documented at
      `accounts/urls.py:29-35` and pinned by `core/tests/test_demo_lockdown.py`.
      Default 10/min. The shadow must sit **before** the
      `path('', include('dj_rest_auth.urls'))` line.
- [x] **A4.** Same treatment for `password/reset/confirm/` — today only
      `password/reset/` is shadowed and throttled, leaving the endpoint that
      *accepts the reset token* open to token brute-forcing. Scope
      `password_reset_confirm`, default 5/hour, `re_path` with `/?$`.
- [x] **A5.** Configure allauth `ACCOUNT_RATE_LIMITS` for `login_failed` as
      defense in depth behind A3.
- [x] **A6.** Audit the scoped-throttle views that *replace* the default
      classes rather than adding to them (`accounts/views.py:35-37, 81-91`;
      `courses/views.py:2248-2250`). Listing only `ClientIPScopedRateThrottle`
      drops the global anon/user ceiling for that endpoint. Make each list the
      global classes alongside the scoped one, matching the pattern
      `join_with_code` already uses (see the comment at
      `courses/views.py:2155-2163`).
- [x] **A7.** [P] Add a secret-scanning step to CI (gitleaks or
      `detect-secrets`) covering the working tree and full history, so item 1
      stays clean. Independent of every other task.

### B. Cross-instructor content exposure — High

`CourseViewSet.get_queryset` (`courses/views.py:81-83`) returns the unfiltered
`Course` queryset to any user with `is_instructor=True`. `IsCourseInstructor`
allows all SAFE methods (`courses/permissions.py:159-161`), so
`GET /api/courses/<any-code>/` serves the full `CourseSerializer` including
nested `units → lessons → content` to an instructor with no relationship to the
course. Course codes are enumerable by design (`ROB101`, `JAVA101`). The same
lesson requested via `GET /api/lessons/<id>/` correctly 403s — two different
answers for the same data.

- [x] **B1.** Keep cross-instructor browsing of the catalog, but strip the
      nested `units`/`lessons` payload from the course-detail response when the
      caller neither owns the course nor is actively enrolled. Follow the
      existing precedent at `courses/serializers.py:517-526`, where
      `enrollment_code` is already popped for non-owners.
- [x] **B2.** Add permission-boundary tests: foreign instructor gets course
      metadata but no lesson content; owning instructor and enrolled student
      get the full payload; anonymous still 401s.

### C. Announcement create has no ownership check — High

`AnnouncementViewSet` (`courses/views.py:898-933`) enforces ownership in
`check_object_permissions`, which only runs for detail routes. `create` never
resolves a course, so `POST /api/courses/announcements/` from any authenticated
student reaches `serializer.save()` unguarded. It currently fails as a database
IntegrityError (non-null `course`/`author`) — a 500, not a 403. That is an
error-shape bug masking a missing authorization check, and it is one serializer
field away from being exploitable.

- [x] **C1.** The real creation path is the course-scoped
      `CourseAnnouncementsView` (`courses/views.py:960-981`), which already
      checks `require_course_instructor`. Disable `create` on the router
      viewset so the unguarded route returns 405 rather than 500. If you
      instead choose to implement it properly, it must resolve the course from
      a validated `course` field and call `require_course_instructor` in
      `perform_create` — mirroring `UnitViewSet.perform_create:231-234`.
- [x] **C2.** Test: student POST to the viewset route gets 405 (or 403 if
      implemented), never 500; instructor creation via the course-scoped route
      still works.

### D. Attachment upload hardening — Medium

`attachment_upload` (`courses/views.py:2998-3089`) checks extension, per-file
size (25 MB) and a 10-per-lesson cap, but unlike the avatar
(`accounts/views.py:145-247`) and slide-import
(`courses/views.py:3327-3452`) paths it has **no content-type check, no
magic-byte verification, no `require_not_demo` guard, and no scoped throttle**.

Decision on file types: `.py`, `.js`, `.json`, `.zip` **stay allowed** — they
are legitimate course material on a platform teaching Python and game dev.
Attachments are served from a private R2 bucket via presigned URLs on a
different origin, so they cannot execute in the application's origin, and
`.svg`/`.html` are already excluded.

- [x] **D1.** Add magic-byte verification for formats that carry a signature:
      images via Pillow `format` + `verify()` (reuse the avatar helper at
      `accounts/views.py:212-229` rather than duplicating it), PDF `%PDF`
      header, zip `PK` header. Treat code and plain-text types as inert — no
      signature to check — but confirm they are not a disguised binary.
- [x] **D2.** Add `require_not_demo(request.user)` — this endpoint is currently
      missing from the demo lockdown entirely.
- [x] **D3.** Add an `attachment_upload` throttle scope with a hardcoded
      default (60/hour), consistent with A1.
- [x] **D4.** Add a total-request size cap so ten near-limit files in one
      multipart request cannot be used as a memory-pressure lever.
- [x] **D5.** Ensure attachments are served with a download disposition and a
      non-executable content type, so a `.js` or `.html`-ish payload cannot be
      rendered inline if bucket configuration ever changes.
- [x] **D6.** Tests for each: disguised binary rejected, demo account 403
      `demo_blocked`, throttle returns 429, oversize request rejected.

### E. Breached-password check — Medium

`AUTH_PASSWORD_VALIDATORS` (`config/settings.py:187-192`) is the four Django
stock validators. There is no breached-password screening. Minimum length
**stays at 8** by decision.

- [x] **E1.** [P] Add a `PwnedPasswordValidator` in `backend/core/` using the
      HIBP k-anonymity range API: SHA-1 the candidate, send only the first 5
      hex characters, match the remainder locally. The password itself never
      leaves the server. Independent of all other tasks.
- [x] **E2.** **Fail open**: on timeout or any network error, allow the
      password and log a warning. A HIBP outage must never block a student from
      resetting their password — reset is most needed when someone is already
      locked out. Use a short timeout (~2s) so password endpoints stay
      responsive.
- [x] **E3.** Register the validator so it applies on registration, password
      change, reset-confirm, and the invite-signup path
      (`courses/views.py:2313-2318`, which already calls `validate_password`).
- [x] **E4.** Tests with the HIBP call mocked: known-breached password rejected,
      clean password accepted, network failure allows through and logs. **No
      test may make a real network call.**

### F. Config guards — Medium

- [x] **F1.** [P] Add a boot-time guard requiring `USE_HTTPS` when
      `DEBUG=False`, mirroring the existing `SECRET_KEY`/`ALLOWED_HOSTS` guard
      at `config/settings.py:28-36`. Today nothing asserts that HSTS, secure
      cookies, SSL redirect and `SECURE_PROXY_SSL_HEADER` are actually on in
      production — all eight settings sit behind one unguarded flag
      (`settings.py:346-357`). Provide an explicit escape hatch for CI, which
      deliberately runs `DEBUG=False` without HTTPS
      (`.github/workflows/ci.yml:61-67`) — an env var such as
      `ALLOW_INSECURE_NON_DEBUG=1`, set only in CI.
- [x] **F2.** [P] Move `SENTRY_DEBUG_ENDPOINT` to an import-time read.
      `config/health.py:70-80` reads it per-request via `decouple.config`, so
      an unauthenticated route that raises `ZeroDivisionError` can be switched
      on without a redeploy. Add it to the `render.yaml` env inventory comment,
      which currently omits it.

### G. Dependencies — Medium

- [x] **G1.** [P] `npm audit fix` in `frontend/` for the react-router
      advisory (GHSA-qwww-vcr4-c8h2, RSC-mode CSRF, affects 7.12.0–7.18.1;
      installed 7.18.1). Two further dev-only highs resolve with it.
- [x] **G2.** After G1, run `python manage.py migrate --check` against Neon.
      Dependency bumps ship third-party migrations; this is a standing rule for
      this project after **any** requirements or lockfile change.
- [x] **G3.** Record that backend `pip-audit` is clean — the only hits are
      against `pip` itself (6 advisories on 25.0.1), which is build tooling,
      not a runtime dependency of the service.

## Frontend tasks

- [x] **H1.** [P] Verify the react-router bump from G1: `npx tsc --noEmit`,
      `npm run lint`, vitest, and a routing smoke test through the app —
      breadcrumbs, the course player, and lazy-loaded instructor routes, since
      the bump touches the data router.
- [x] **H2.** [P] Surface the new backend rejections in the attachment upload
      UI: 429 (throttled) and 403 `demo_blocked` need real messages, not a
      generic failure. The `demo_blocked` toast plumbing already exists at
      `services/api.ts:70-90, 118-122`.
- [x] **H3.** [P] Add a shape check to `navigate(notification.related_url)`
      (`components/notifications/NotificationBell.tsx:84-85`), which today
      follows an API-supplied string with no validation. `related_url` is
      server-set and read-only so this is defense in depth, not an open hole —
      accept a relative in-app path only.

## Accepted risks — documented, no code change

Each of these was reviewed during the audit and consciously accepted.

1. **Auth tokens in localStorage** (item 10). Access and refresh JWTs live in
   `localStorage` (`services/auth.ts:7-8`), set deliberately via
   `JWT_AUTH_HTTPONLY: False` (`settings.py:469`). Mitigating factors: no
   `dangerouslySetInnerHTML` or other XSS sink anywhere in the frontend, CSP is
   `default-src 'none'` / `script-src 'self'` (`settings.py:369-381`), access
   tokens live 60 minutes, and refresh rotation with blacklisting is on. The
   hybrid (refresh-token-to-cookie) and full-cookie migrations were both
   considered and declined for this phase.
2. **Email verification optional** (item 13). `ACCOUNT_EMAIL_VERIFICATION`
   stays `optional` and no gate reads `EmailAddress.verified`. Deferred
   specifically because email deliverability is an open problem — `_dmarc` and
   root SPF records are still absent and invite deliverability is untested.
   Making verification mandatory before mail delivery is reliable would convert
   a security control into an availability outage: students could not complete
   signup if the verification message never arrives. Public registration is
   disabled in production (`ALLOW_REGISTRATION` defaults False) and the
   invite-accept path proves address ownership through token possession, so
   present-day exposure is near zero.
   **Revisit trigger — whichever comes first:** DMARC/SPF are fixed and
   deliverability is verified, **or** before `ALLOW_REGISTRATION` is ever
   enabled in production. Do not enable public registration without closing
   this first.
3. **Sequential integer IDs** (item 14). URLs use sequential PKs, but the audit
   found no endpoint where guessing an ID bypasses a check: nested lookups are
   parent-scoped (`pk=..., lesson=lesson`) and the remainder are
   ownership-guarded. Course codes are human-chosen and enumerable by design.
   A UUID migration is large and unjustified without a proven exposure.
4. **Presigned R2 URLs survive unenrollment.** An issued URL stays valid for
   its TTL (default 3600s) regardless of later unenrollment or unit re-locking.
   Shortening the TTL is the only cheap lever and was not taken.
5. **Demo guard is opt-in.** `core/demo.py:85-92` documents that any new write
   endpoint forgetting `require_not_demo` is unguarded. Task D2 fixes one such
   omission; converting to default-deny middleware is out of scope.
6. **Upload verification only reads the first 512 bytes** (`core/uploads.py`,
   `_HEADER_BYTES`). A `.py` or `.txt` with a clean preamble and arbitrary
   binary appended past that offset passes. Raised by the phase 73 adversarial
   pass as SUSPICIOUS and accepted: header inspection is what the task
   specified, attachments are never executed server-side, and they are served
   with a download disposition. Reading whole files on upload would trade a
   shallow check for a memory-pressure lever.
7. **A zip whose trailing bytes contain HTML passes** the `.zip` signature
   check, since both that check and the HTML sniff look only at the header.
   Not exploitable through browser MIME sniffing, which requires the markup
   near the start of the resource rather than after a binary header. Same
   adversarial pass, also accepted.

### Fixed during the review round (not deferred)

- **A5 was inert config.** `ACCOUNT_RATE_LIMITS['login_failed']` never ran:
  allauth consumes it in `DefaultAccountAdapter.pre_authenticate()`, and
  dj-rest-auth's `LoginSerializer` calls `django.contrib.auth.authenticate()`
  directly without touching the adapter — proven by nine failed attempts on one
  account followed by a successful login. The setting is removed (with a test
  pinning its absence so it does not come back) and replaced by
  `core.throttling.LoginEmailRateThrottle` on a `login_email` scope, which runs
  in DRF's pipeline and is exercised by a test that attacks one account from
  four different addresses.
- **A `.py` file with a shebang was rejected.** `#!` was in
  `EXECUTABLE_SIGNATURES`, so `#!/usr/bin/env python3` — the ordinary first
  line of a starter script, and exactly the material task D chose to keep
  uploadable — got a 400. The endpoint test passed only because it uploaded a
  shebang-less script. Removed from the signature list; both the unit and
  endpoint tests now use a real shebang.
- **The HTML marker list was too wide after the first fix.** Extending it to
  the full WHATWG sniffing set meant `<div`, `<p`, `<br`, `<table` — how
  ordinary markdown opens — were refused. Narrowed to tags that carry or load
  something, with accepted-case tests so the next tightening does not
  reintroduce the false positive.
- **Per-IP rates would have broken a classroom.** Throttle idents are the
  client address and a school NAT is one bucket, so `login` at 10/min 429'd the
  eleventh student of a period and `join_code` at 10/hour capped a class at ten
  joins an hour — on the endpoint whose only purpose is that flow. Raised to
  30/min and 60/hour. Both were among the never-set scopes, so this default is
  what production will actually run.
- **Attachment errors never reached the instructor.** The endpoint reports
  per-file rejections as `error`, but the frontend read only DRF's `detail`, so
  every content-mismatch and oversize message fell back to a generic string —
  and the test mocked a `detail` shape the API never sends. Both fixed.
- **D5 was half-implemented.** `download_url` set the disposition but not a
  content type, and its test asserted only that a URL was truthy (which passes
  under the local storage fallback that never sets either). It now pins
  `application/octet-stream` too, with a stub-storage test that records the
  parameters.
- **`slide_import` had no throttle test**, before or after this phase — a
  scoped throttle with no `throttle_scope` on the view is silently inert, which
  is the exact bug found in `attachment_upload` during implementation. Covered.

### Fixed during the adversarial pass (not deferred)

- **BROKEN — `HTML_MARKERS` missed most sniffable tags.** The first
  implementation matched only `<!doctype html`, `<html`, `<script`, `<svg`, so
  an `<iframe src="javascript:...">` uploaded as `.txt` was stored with a 201,
  and a UTF-8 BOM walked past the ASCII-only `lstrip()`. Replaced with the
  WHATWG sniffing tag set plus BOM handling and a tag-terminator rule, and
  pinned by `core/tests/test_uploads.py` and an end-to-end case posting the
  exact payload that used to succeed.
- **`ACCOUNT_RATE_LIMITS` was enforced per gunicorn worker.** allauth reads the
  `default` cache alias, which was `LocMemCache`, so the account-keyed
  `login_failed` ceiling was really double its configured value — the phase 63
  bug arriving through a different door. The default alias is now file-backed
  and shared, guarded by three tests in `core/tests/test_throttling.py`.

## Verification

Run `/verify-stack` and show the output. Beyond a green suite, this phase is
proven by these specific checks:

**Rate limiting (A)**
- [ ] New test: with **no** throttle env vars set, `DEFAULT_THROTTLE_RATES` has
      no `None` value. This is the regression guard for the whole class of bug.
- [ ] New test: repeated failed logins to `POST /api/auth/login/` return 429.
- [ ] New test: the same, to **`/api/auth/login`** with no trailing slash —
      this is the specific bypass the `re_path` shadow exists to prevent, and
      the reason A3 must not use `path()`.
- [ ] Same slash/no-slash pair for `password/reset/confirm`.
- [ ] Full suite still green after the A2 conftest fixture — confirm the pass
      count is at least the 1181 baseline and that no test 429s spuriously.

**Authorization (B, C)**
- [ ] `pytest backend/courses/tests/ -k "instructor and course_detail"` —
      foreign instructor receives course metadata without nested lesson
      content; owner and enrolled student receive the full payload.
- [ ] Student POST to `/api/courses/announcements/` returns 405/403, **never
      500**. Confirm via response status, not just absence of an exception.
- [ ] Per `.claude/rules/backend.md`, every new or changed endpoint has a test
      covering instructor vs student vs anonymous.

**Uploads (D)**
- [ ] A renamed binary (e.g. an ELF or PNG saved as `.pdf`) is rejected.
- [ ] A genuine `.py` and a genuine `.zip` still upload — guard against
      over-correcting and breaking real coursework.
- [ ] Demo account gets 403 with `code: demo_blocked`.
- [ ] Exceeding the attachment throttle returns 429.

**Passwords (E)**
- [ ] Known-breached password (`Password123`) rejected at registration,
      change, reset-confirm, and invite signup.
- [ ] Mocked HIBP timeout allows the password and emits a warning log.
- [ ] Confirm no test performs a real network call to `api.pwnedpasswords.com`.

**Config (F)**
- [ ] `DEBUG=False` without `USE_HTTPS` raises `ImproperlyConfigured` at boot.
- [ ] CI still passes with its documented escape hatch set.
- [ ] `/api/sentry-debug/` 404s and cannot be enabled without a redeploy.

**Dependencies (G)**
- [ ] `npm audit --omit=dev` reports zero high/critical.
- [ ] `docker compose exec -T backend pip-audit` — clean apart from `pip`.
- [ ] `migrate --check` against Neon is clean after the bump.

**Manual flow (browser)**
- [ ] As a student: log in, open a course, read a lesson, post a discussion
      reply — confirm normal use is unaffected by the new throttles.
- [ ] As an instructor: upload a `.py` attachment to a lesson and confirm it
      succeeds and downloads intact.
- [ ] As the demo account: attempt an attachment upload and confirm the
      demo-blocked toast appears.
- [ ] Confirm the throttle counters do not leak across the two gunicorn
      workers — the file-backed cache at `settings.py:169-184` is shared, so a
      limit of 10/min must mean 10 total, not 10 per worker.

## Notes for the implementer

- Backend changes need `docker compose restart backend` to take effect.
- Backend tests run in Docker: `docker compose exec -T backend pytest` — there
  is no host Python.
- No model changes are expected in this phase, so no migrations. If you find
  yourself writing one, stop and reconsider — and remember that any new NOT
  NULL column needs `db_default` to survive the migrate-then-deploy window.
- Review agents tend to leave probe/scratch test files behind. Read
  `git status` before staging; never `git add -A` blind.
- Merging to `main` deploys the backend. **A1 changes production rate limits
  the moment it merges** — the hardcoded defaults become live for any scope
  whose env var is unset, which today includes `join_code` and `invite_link`.
  That is the intended fix, but expect the behavior change and verify the two
  affected flows in production after deploy.
