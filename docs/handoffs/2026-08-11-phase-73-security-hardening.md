# Handoff: Phase 73 — security hardening audit

## Current state
**Phase 73 is code-complete and verified; PR not yet open** (the push was
blocked mid-session and is the first thing to finish). Branch
`phase-73-security-hardening`, 5 commits off `lms/main` at `65c33cb`.

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

Verify: pytest **1246 passed** (baseline 1181), tsc **0**, lint **0 errors**
(known react-refresh warning), vitest **26 files / 268 passed**, `npm audit
--omit=dev` **0 vulnerabilities**, `pip-audit` clean except `pip` itself.
**No migrations.** Live smoke test on localhost: login throttle fires
(9×400 → 429) and the no-slash `/api/auth/login` shares the bucket.

## In progress / not done
1. **Push + PR.** `git push -u lms phase-73-security-hardening` was denied by
   the permission classifier. Nothing else blocks the PR.
2. **Review findings.** code-reviewer and adversarial-tester were still running
   at handoff; fold in anything BROKEN before merging, list SUSPICIOUS in the
   PR body.
3. Adversarial probe files `backend/{accounts,courses}/test_zz_probe73*.py`
   must be deleted if still present — never commit them.

## Next steps
1. Push the branch and open the PR against main.
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

## Files to read first
1. `docs/specs/phase-73-security-hardening-audit.md` — 20-item table, accepted
   risks, verification.
2. `backend/conftest.py` — why throttling is off in tests.
3. `backend/core/uploads.py` and `backend/core/password_validation.py`.
4. `backend/accounts/urls.py` — the optional-slash shadow pattern.
