# Handoff: Phase 56 — demo sandbox security

## Current state

Phase 56 complete. **PR #74 open, not merged**:
https://github.com/Cesar6060/LMS/pull/74
Branch `feat/phase-56-demo-sandbox-security`, 2 commits, 21 files.
All spec checklist items done except the four that are post-merge by
nature (manual click-through, reset-workflow dispatch, prod rollout).
`docs/specs/phase-56-demo-sandbox-security.md` has an "Outcome" section
and a `B2b` section recording every finding fixed mid-phase.

`/verify-stack` PASS: **609 backend tests** (was 569), **57 frontend
tests** (was 50), `tsc` 0 errors, `eslint` 0 errors, coverage 94%.

Landed: central `core/demo.py` + `core/permissions.py` with the five
legacy `email ==` sites refactored onto it; identity/shared-surface
writes blocked (enrollment create both paths + update, profile on both
routes, settings, avatar upload/delete, gamification mascot, all
discussion writes); learning writes explicitly allowed and pinned;
one `demo_blocked` denial contract; per-IP throttle keying for demo
traffic; registration sub-path stubs; `is_demo` on `UserSerializer`;
nightly reset workflow; demo banner + central blocked-write toast +
disabled controls on the frontend.

## Blocking prerequisite before the reset workflow can run

**Add a `DEMO_ACCOUNT_PASSWORD` repo secret to `Cesar6060/LMS`** (remote
`lms`), set to the same value as the Render env var. Confirmed absent —
`gh secret list` shows only `NEON_DATABASE_URL` and the four R2 secrets.

Why it matters: `seed_demo_account` re-asserts the demo password from
`settings.DEMO_ACCOUNT_PASSWORD`, which falls back to the published
`Admin123!` default when unset. An unconfigured nightly run would
silently un-rotate the production demo password and undo phase 44. The
workflow's first step hard-fails with a clear error until the secret
exists — loud, not silent, but it does mean every scheduled run fails
until someone adds it.

## In progress / not done

- **Manual click-through not performed** (local or prod). The flow is in
  the spec's Verification section. Most worth doing by hand: the demo
  banner on a real demo login, one blocked write showing the friendly
  toast rather than a raw error, and confirming a normal student can
  still post a reply and edit their profile.
- **Reset workflow never executed.** Dispatch it once via
  `workflow_dispatch` after the secret exists and the PR is merged, and
  confirm it exits 0 with DEMO101 enrollment intact and Unit 1 complete.
- **47 merged remote `lms/*` branches still unpruned** — carried over
  from phase 55, still deliberate.

## Next steps

1. Add the `DEMO_ACCOUNT_PASSWORD` secret (see above).
2. Merge PR #74, let Render deploy. **No migrations this phase**, so the
   deploy order is boring — no repeat of phase 55's subtractive-migration
   ordering trap.
3. Dispatch `demo-reset.yml` once, confirm green.
4. Click through the live demo on stemquests.com: banner visible, one
   blocked write, one allowed write.
5. Phase 57: Django 4.2 → 5.2 LTS (4.2 is past EOL; 4.2.30 is its final
   patch). This is the item phase 55 had slotted as 56.
6. Phase 57b (or fold in): react-router 7 → 8, needs React 18 → 19.
7. Dependabot PRs still need triage — carried from phase 55.

## Decisions made

- **Interactive sandbox over read-only.** Blocking every write would have
  made the demo useless — quizzes and lesson completion are the product.
  The line is: writes that advance *your own* learning stay open; writes
  that change identity or what other visitors see are refused.
- **Discussions are read-only for the demo.** Posting was the one allowed
  write where one visitor's content is displayed to strangers — a spam,
  abuse, and phishing-link vector that a nightly reset only bounds rather
  than prevents. Browsing seeded threads still demonstrates the feature.
- **No `is_demo` DB column.** One account, and the email comparison was
  already the identity all five legacy checks used. A migration would add
  drift risk (seed must set it, prod row must be backfilled) for no
  enforcement gain. Centralization happened in code instead.
- **Reset at 08:47 UTC, 30 minutes after the 08:17 backup**, so the
  morning dump always captures pre-reset state and a bad reset is
  recoverable from the same day's backup.
- **`accept_invite` left alone** and recorded in the spec's Out of scope.
  It is a throttled, token-gated account-creation path that legitimately
  works independently of `ALLOW_REGISTRATION` — writing that down so the
  next audit stops re-flagging it.
- **Password-change denial moved 400 → 403 `demo_blocked`**, so every
  blocked demo write surfaces the same friendly message. No UI impact:
  `authService.changePassword` has no caller in `frontend/src`.

## Gotchas discovered

- **dj-rest-auth mounts its views with an optional trailing slash
  (`r'user/?$'`), so a `path()` shadow only captures one spelling.** The
  bare `/api/auth/user` fell through to the *unshadowed* original and a
  demo `PATCH` renamed the shared account with a 200. The same root cause
  had been silently skipping the `password_reset` throttle on
  `/api/auth/password/reset` since phase 51. Any future shadow of a
  dj-rest-auth view must use `re_path(r'^…/?$', …)`, and the real lesson
  is to guard at the shared choke point (the serializer) rather than
  trusting URL shadowing alone.
- **`password/change/` and `password/reset/confirm/` are two write paths
  to the same password.** Phase 42 protected only the first. Anything
  that must never change a password needs both
  `PASSWORD_CHANGE_SERIALIZER` and `PASSWORD_RESET_CONFIRM_SERIALIZER`.
- **`seed_demo_account` re-asserts the password on every run**, so any
  automation running it must supply `DEMO_ACCOUNT_PASSWORD` or it
  silently reverts prod to the published default.
- **A guard on a viewset's `create`/`destroy` is not a guard on
  `update`.** `EnrollmentViewSet.update` was unguarded and returned 200
  as a silent no-op — invisible today because every field is read-only,
  and it would have reopened the moment a writable field appeared.
- **Concurrent pytest runs in the same container collide** on
  `test_gamedev_db` ("database is being accessed by other users"). It
  looks like ~90 test errors and is not a code failure. Drop the DB with
  `docker compose exec -T db psql -U gamedev_user -d gamedev_db -c "DROP
  DATABASE IF EXISTS test_gamedev_db;"` (the role is `gamedev_user`, not
  `postgres`).
- The axios interceptor runs outside React, so the demo-blocked toast
  needs a module-level listener bridge registered by `ToastContext`.

## Files to read first

1. `docs/specs/phase-56-demo-sandbox-security.md` — "B2b", "Outcome", and
   the Verification section's remaining unchecked items.
2. `backend/core/demo.py` — the whole policy's identity check, and the
   `demo_blocked` body that is a contract with the frontend.
3. `backend/core/tests/test_demo_lockdown.py` — 40 tests stating the
   entire policy in one place: blocked, allowed, and normal-user
   regression.
4. `.github/workflows/demo-reset.yml` — the secret guard and the
   backup-ordering rationale in the header.
5. `frontend/src/services/api.ts` — `isDemoBlocked` and the listener
   bridge.
