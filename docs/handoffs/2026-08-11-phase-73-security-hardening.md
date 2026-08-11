# Handoff: Phase 73 — security hardening audit

## Current state
**Phase 73 is code-complete, reviewed, verified. PR #106 is open and NOT
merged.** https://github.com/Cesar6060/LMS/pull/106 — branch
`phase-73-security-hardening`, 6 commits off `lms/main` at `65c33cb`.

Audited all 20 checklist items: 14 came back clean, 3 were accepted risks, 6
produced fixes. Spec `docs/specs/phase-73-security-hardening-audit.md` carries
the full per-item table and every checklist box is ticked.

What shipped:
- **Throttling (Critical).** Every scope in `DEFAULT_THROTTLE_RATES` defaulted
  to `None` = unlimited, so a missing Render var silently disabled a rate limit
  — `THROTTLE_JOIN_CODE`/`THROTTLE_INVITE_LINK` were live in that state. All
  now carry real defaults. New `login` and `password_reset_confirm` scopes
  mounted as `re_path` optional-slash shadows, plus allauth
  `ACCOUNT_RATE_LIMITS`. New `backend/conftest.py` disables throttling under
  pytest (opt back in with `@pytest.mark.throttled`).
- **Authorization.** `CourseSerializer` strips nested units/lessons for callers
  who neither own the course nor are enrolled (any `is_instructor` account
  could read every course's content). `AnnouncementViewSet.create` closed — it
  checked no ownership and 500'd on a DB constraint.
- **Uploads.** New `backend/core/uploads.py`; attachments now verify content
  against the claimed extension, plus the missing demo guard, a scoped
  throttle, and a total-request size cap. Avatar path refactored onto it.
- **Passwords.** `core/password_validation.py` — HIBP k-anonymity screening,
  fails open on any error.
- **Config.** `USE_HTTPS` boot guard when `DEBUG=False` (CI opts out via
  `ALLOW_INSECURE_NON_DEBUG`); `SENTRY_DEBUG_ENDPOINT` moved to import-time.
- **Deps/CI.** react-router 7.18.1→7.18.2 (GHSA-qwww-vcr4-c8h2); gitleaks
  workflow scanning tree + full history.

Verify (post-review re-run): pytest **1310 passed** (baseline 1181), tsc
**0**, lint **0 errors** (known react-refresh warning), vitest **26 files /
269 passed**, `npm audit --omit=dev` **0 vulnerabilities**, `pip-audit` clean
except `pip` itself. **No migrations.** Live checks: the per-IP login throttle
fires and the no-slash `/api/auth/login` shares its bucket; the per-account
throttle fires at 20, still refuses the correct password once tripped, and
leaves other accounts working.

## In progress / not done
1. **PR #106 is not merged.** Both review agents ran; every BROKEN and HIGH
   finding is fixed and re-verified. Deferred items are listed in the PR body
   and the spec's accepted-risks section, not dropped.
2. Two review LOWs left open on purpose: media signature coverage (MPEG-2 mp3
   frame syncs, `.mov` files whose first atom is `moov` rather than `ftyp`)
   and RFC 5987 filenames, so a `Práctica.pdf` downloads as `Pr_ctica.pdf`.

## Next steps
1. Review and merge PR #106.
2. **Before merging, know that A1 changes production behaviour**: scopes whose
   env var was never set (join_code, invite_link) stop being unlimited on this
   deploy. That is the fix, but verify both flows after deploy.
3. `USE_HTTPS` is confirmed already set in Render (prod returns the HSTS value
   from inside that block), so the new boot guard will not abort the deploy.
   Do **not** set `ALLOW_INSECURE_NON_DEBUG` in Render.
4. Phase 72 (content-upsert hardening) is still unstarted.
5. Carried owner actions, untouched: Neon `production` `protected: false`;
   `_dmarc` + root SPF absent; invite-deliverability test; JAVA101 answer
   rotation.

## Decisions made
- **allauth's `ACCOUNT_RATE_LIMITS` does not work on this stack.** It is
  consumed in `DefaultAccountAdapter.pre_authenticate()`, and dj-rest-auth
  calls `django.contrib.auth.authenticate()` directly, so it never runs. Do
  not re-add it believing it protects login; a test now pins its absence. The
  per-account ceiling lives in `core.throttling.LoginEmailRateThrottle`.
- **Throttle rates must survive a school NAT.** Idents are the client address,
  so a classroom is one bucket. That is why `login` is 30/min and `join_code`
  60/hour rather than the tighter numbers render.yaml used to suggest.
- Tokens stay in localStorage; email verification stays `optional` — both
  accepted risks recorded in the spec. Verification is deferred specifically
  because mail deliverability is unresolved; making it mandatory would turn a
  security control into a signup outage. **Revisit before enabling
  `ALLOW_REGISTRATION` in prod.**
- Password minimum stays 8 — a longer floor pushes school-age students toward
  reuse; breach screening is the stronger signal.
- `.py`/`.js`/`.zip` stay uploadable: they are ordinary material on a platform
  teaching Python, and attachments are cross-origin on a private bucket. The
  check is that bytes match the extension, not that the extension is inert.
- HIBP defaults **off under pytest** (7 existing tests would otherwise send
  fixture password hashes to a third party). Production unaffected.

## Gotchas discovered
- **Concurrent pytest runs collide** on `test_gamedev_db` and produce hundreds
  of bogus errors. If a subagent is running tests, wait — do not debug it.
- DRF binds `THROTTLE_RATES` to the class at import, so `override_settings`
  does not reach it; patch the class attribute.
- A scoped throttle listed alone *replaces* `DEFAULT_THROTTLE_CLASSES`. Also,
  `@throttle_classes` without `view.cls.throttle_scope` is silently inert.
- `can_access_course()` in a serializer issues its own query and trips the
  phase-63 query-count guard; reuse the prefetch-aware `is_enrolled`.
- Shell cwd persists between Bash calls — `cd` to the repo root before `git add`.
- A scoped throttle is silently inert without `view.cls.throttle_scope`; this
  bit `attachment_upload` during implementation and `slide_import` had never
  been tested at all.
- Hardening a content check by widening a blocklist cuts both ways: the full
  WHATWG HTML-sniffing set rejects markdown that opens with `<div>` or `<p>`.
  The accepted-case tests in `core/tests/test_uploads.py` exist to stop that
  being "fixed" back in.

## Files to read first
1. `docs/specs/phase-73-security-hardening-audit.md` — 20-item table, accepted
   risks, verification.
2. `backend/conftest.py` — why throttling is off in tests.
3. `backend/core/uploads.py` and `backend/core/password_validation.py`.
4. `backend/accounts/urls.py` — the optional-slash shadow pattern.
