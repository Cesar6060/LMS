# Handoff: Phase 56 — demo sandbox security

## Current state

Phase 56 complete, **merged and deployed**. PR #74 merged as `afa91de`;
Render auto-deployed from `main` and the new build is confirmed live.
`docs/specs/phase-56-demo-sandbox-security.md` has "Outcome", a `B2b`
section for findings fixed mid-phase, and a "Production incident" section.

`/verify-stack` PASS: **615 backend tests** (was 569), **57 frontend
tests** (was 50), `tsc` 0 errors, `eslint` 0 errors, coverage 94%.

**Verified against production after the deploy** (not just locally):
`PATCH /api/auth/profile/`, `/api/auth/user/`, and the bare
`/api/auth/user` all return `403 demo_blocked`; `GET /api/auth/user/`
200; the shared account is intact as "Jordan Doe" with `is_demo: true`;
`/api/health/?deep=1` 200 with `database: ok`; stemquests.com serves.

## Production incident found and closed during rollout

`DEMO_ACCOUNT_PASSWORD` was **absent from Render entirely**, so prod was
running the committed `Admin123!` default and raw login with
`jdoe@demo.com / Admin123!` returned 200 with a JWT pair. Phase 44's
rotation had been lost, most likely in the phase-49 region move. Fixed:
variable set on Render + as a GitHub secret, `seed_demo_account` run as a
Render one-off job. Old password now **400**, demo-login still **200**.

Nothing in the deploy pipeline re-seeds (`render.yaml:42-43` is pip
install → collectstatic → gunicorn), so redeploying can never rotate the
password — only the management command does.

The account audit that phase 42 deferred is now done: 5 users, 2
instructors (the operator, and `instructor@demo.com` which owns DEMO101
and has **no usable password**). That audit surfaced a separate hole,
fixed in `9462109` — see Gotchas.

Landed: central `core/demo.py` + `core/permissions.py` with the five
legacy `email ==` sites refactored onto it; identity/shared-surface
writes blocked (enrollment create both paths + update, profile on both
routes, settings, avatar upload/delete, gamification mascot, all
discussion writes); learning writes explicitly allowed and pinned;
one `demo_blocked` denial contract; per-IP throttle keying for demo
traffic; registration sub-path stubs; `is_demo` on `UserSerializer`;
nightly reset workflow; demo banner + central blocked-write toast +
disabled controls on the frontend.

## Migrations — production is now fully applied

Phase 56 added **no migrations of its own**. But a `migrate --check`
against production during close-out **failed**: one migration was
outstanding, `token_blacklist.0013_alter_blacklistedtoken_options_and_more`.

It arrived with phase 55's simplejwt 5.5.1 bump (A1) and was missed
because that deploy only applied the `courses` migration anyone had
thought about. It is purely `AlterModelOptions` (verbose names and
`ordering`), so it emits **no SQL** and its absence had zero runtime
effect — Meta options come from the installed package's models.py, not
from migration state. The only real consequence was that `migrate
--check` failed and any future `token_blacklist` migration would have
been blocked behind it.

Applied 2026-07-28 via a Render one-off job; `migrate --check` now exits
0. `makemigrations --check --dry-run` is also clean locally.

**Lesson worth keeping:** a dependency bump can introduce third-party
migrations. `pip-audit` and the test suite both stay green while they sit
unapplied. Run `migrate --check` against Neon after any requirements
change, not just after writing your own migration.

## In progress / not done

- **`demo-reset.yml` has never executed.** It is registered on `main` and
  both required secrets exist, so it is ready — but nobody has run it.
  Deliberately left for a human: `--reset` deletes visitor-generated
  production data, which is not something to fire off as a verification
  step. Dispatch it once via `workflow_dispatch` and confirm it exits 0
  with DEMO101 enrollment intact and Unit 1 complete. Until then the
  nightly cron will do the first run unattended at 08:47 UTC.
- **Browser click-through not performed.** The API-level behavior is
  verified against production (above), but nobody has looked at the demo
  banner, the blocked-write toast, or the disabled Settings controls in
  an actual browser.
- **47 merged remote `lms/*` branches still unpruned** — carried over
  from phase 55, still deliberate.

## Next steps

1. Dispatch `demo-reset.yml` once and confirm green — the last unchecked
   verification item.
2. Click through the live demo on stemquests.com: banner visible, one
   blocked write showing the friendly toast, one allowed write.
3. Phase 57: Django 4.2 → 5.2 LTS (4.2 is past EOL; 4.2.30 is its final
   patch). This is the item phase 55 had slotted as 56.
4. Phase 57b (or fold in): react-router 7 → 8, needs React 18 → 19.
5. Dependabot PRs still need triage — carried from phase 55.
6. Consider an origin-lock between Cloudflare and Render (IP allowlist or
   a shared secret header verified in `ClientIPIdentMixin`). Every
   throttle depends on `CF-Connecting-IP` being unspoofable, which today
   rests entirely on Cloudflare fronting every request. Verified still
   true this session (a request carrying that header to the API is
   rejected at the edge with `error code: 1000` / 403), but it is an
   infra assumption with no code-side enforcement.

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
  silently reverts prod to the published default. This is not
  hypothetical — it is exactly how prod ended up back on `Admin123!`.
- **allauth's `ResetPasswordForm` does not exclude accounts with unusable
  passwords**, unlike Django's own `PasswordResetForm.get_users()`. So an
  account created with `set_unusable_password()` — meant to be
  un-loggable — could be handed a working password by reset. That applied
  to `instructor@demo.com`, whose mail would go to a `demo.com` mailbox
  nobody here controls, yielding an instructor account with every course,
  roster, and grade. Fixed in `9462109`; if social auth or a "set your
  password via reset" onboarding is ever added, revisit that skip.
- **`render ssh` cannot be scripted** ("can only be used in interactive
  mode"). To run a management command on prod non-interactively use
  `render jobs create <srv-id> --start-command "..."` and read output
  with `render logs -r <job-id>`. The service is
  `srv-d9go1em1a83c73f50r2g`, `rootDir: backend`.
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
