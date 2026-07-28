# Phase 56 — Demo sandbox security

## Goal

Make the shared public demo (`jdoe@demo.com` in DEMO101) safe against a
malicious or careless visitor without making it feel dead. Today the demo
lockdown is five ad-hoc `email ==` checks; every endpoint added since is
writable by default. This phase centralizes demo enforcement into one
permission layer, blocks the identity/shared-surface writes (profile rename,
avatar upload, settings, enrollment into other courses, all discussion
posting) while keeping the learning writes that make the demo work (lesson
progress, quizzes, notification read-marks), fixes the shared throttle bucket
where all demo visitors contend for one 120/min allowance, adds the automated
nightly reset the Terms page already promises, and gives demo sessions a
visible banner plus friendly "not available in the demo" errors instead of
raw 403s.

Decisions from the planning interview: **interactive sandbox** (learning
writes allowed, identity writes blocked); discussions **read-only** for the
demo account; reset via **GitHub Actions cron**; UI gets **banner + friendly
errors**.

Note: this takes the phase-56 slot; the Django 4.2 → 5.2 upgrade named in the
phase-55 handoff shifts to phase 57.

## Out of scope

- Per-visitor sandboxed demo accounts — one shared account remains.
- An instructor-role demo account.
- Changes to `accept_invite` (`backend/courses/views.py:1750-1847`). It is a
  deliberate, throttled (`invite_accept` 10/hour), token-gated account-creation
  path independent of `ALLOW_REGISTRATION` — accepted as-is; recorded here so
  the next audit doesn't re-flag it as an oversight.
- httpOnly-cookie token transport (still deferred from phase 43/44).
- Private R2 bucket / signed URLs for lesson attachments (deferred since 42).
- Any change to demo seeding content (`clone_course_for_demo`, baseline
  progress shape).
- An `is_demo` DB column. Enforcement stays keyed on
  `settings.DEMO_ACCOUNT_EMAIL` — one account, already the identity used by
  all five existing checks; a migration adds drift risk (seed must set it,
  prod row must be backfilled) for no enforcement gain. Centralization
  happens in code, not the schema.

## Backend tasks

### B1. Central demo helper + permission class

- [x] `backend/core/demo.py`: `is_demo_user(user) -> bool` — authenticated and
      `user.email == settings.DEMO_ACCOUNT_EMAIL`. Single source of truth.
- [x] `backend/core/permissions.py`: `NotDemoAccountForWrites` — allows safe
      methods (GET/HEAD/OPTIONS) for everyone; denies unsafe methods for the
      demo user with `PermissionDenied(detail=..., code='demo_blocked')`.
      The response must carry a machine-readable marker the frontend can key
      on (DRF renders `code` into the exception; verify the JSON shape in a
      test and pin it — the frontend depends on it).
- [x] Refactor the five existing call sites to use `is_demo_user()` —
      behavior unchanged, verified by the existing tests:
      `backend/courses/views.py:438` (unenroll refuse),
      `backend/accounts/serializers.py:167-181` (password change),
      `backend/accounts/serializers.py:107-116` (reset-email skip),
      `backend/core/email.py:35-47` (triggered-by suppression),
      `backend/courses/views.py:1655-1661` (invite marks demo invalid).

### B2. Block identity / shared-surface writes (each item: demo → 403 with
`demo_blocked` code; a normal student → unchanged behavior; both tested)

- [x] Enrollment creation, **both** join paths:
      `EnrollmentViewSet.create` (`backend/courses/views.py:413-421`) and
      `CourseViewSet.enroll` (`backend/courses/views.py:88-128`). Closes the
      "demo account joins JAVA101 with a leaked enrollment code" hole that
      A4 left half-open (destroy blocked, create not).
- [x] Profile writes: `PUT/PATCH /api/auth/profile/`
      (`backend/accounts/views.py:81-99`) **and** dj-rest-auth's
      `PUT/PATCH /api/auth/user/` (mounted via `accounts/urls.py:24`) — both
      routes use `UserSerializer`; block both, don't forget the second.
- [x] Settings write: `PUT/PATCH /api/auth/settings/`
      (`backend/accounts/views.py:102-126`).
- [x] Avatar upload + delete: `POST /api/auth/settings/avatar/`,
      `DELETE /api/auth/settings/avatar/delete/`
      (`backend/accounts/views.py:129-245`). Blocks per-visitor 5 MB writes
      to shared storage.
- [x] Gamification avatar/mascot: `PATCH /api/gamification/avatar/`
      (`backend/gamification/views.py:48-100`) — the free-text mascot name
      (1–20 chars) is shared state another visitor sees; treat as identity.
- [x] Discussions, all writes: thread create/update/delete and reply
      create/update/delete (`backend/discussions/views.py:23,54,133,174`).
      Demo account keeps read access to seeded threads.
- [x] Explicitly **allowed** for demo (pin each with a test so a future
      permission sweep doesn't break the demo): lesson progress
      (`courses/views.py:448-490`), course activity ping
      (`courses/views.py:1850-1852`), lesson-quiz session start/answer
      (`courses/views.py:2301-2369`), unit-quiz submit + session
      (`quizzes/views.py:166-462`), notification read/mark-all-read
      (`notifications/views.py:29-53`), logout.

### B3. `is_demo` in the API payload [P]

- [x] `UserSerializer` (`backend/accounts/serializers.py:42-61`): add
      read-only computed `is_demo` via `is_demo_user()`. Comes along for free
      on demo-login, `/api/auth/user/`, and profile responses.
- [x] Test: demo user payload has `is_demo: true`; normal user `false`.

### B4. Throttle fixes [P]

- [x] `ClientIPUserRateThrottle` (`backend/core/throttling.py:48-54`): for the
      demo user, key the cache on client IP instead of `user.pk`, so N
      visitors get N buckets instead of contending for one shared 120/min
      allowance (self-DoS / griefing vector). Normal users keep pk-keyed
      behavior.
- [x] Delete the stale comment at `backend/config/settings.py:224-226`
      claiming authenticated demo traffic is never throttled (phase 51 made
      the opposite true); replace with one sentence describing the per-IP
      demo keying.
- [x] Tests: two IPs as the demo user throttle independently; one IP still
      throttles; a normal user is keyed by pk regardless of IP.

### B5. Registration stub sub-paths [P]

- [x] When `ALLOW_REGISTRATION` is off, `/api/auth/registration/verify-email/`
      and `/api/auth/registration/resend-email/` currently 404 (the stub at
      `backend/accounts/urls.py:5-11` is exact-path). Mount stubs so they
      return the same 403 payload as `registration_disabled` — the frontend
      still calls them (`frontend/src/services/auth.ts:71-77`).
- [x] Tests: both sub-paths → 403 when off; real routes still mount when
      `ALLOW_REGISTRATION=True` (existing on-path test keeps passing).

### B6. Automated nightly reset [P]

- [x] `.github/workflows/demo-reset.yml`: cron `47 8 * * *` (daily, ~30 min
      after `db-backup.yml`'s `17 8 * * *` so the morning backup always
      captures pre-reset state and a bad reset is recoverable) plus
      `workflow_dispatch` for manual runs. Job: checkout, set up Python,
      `pip install -r backend/requirements.txt`, run
      `python manage.py seed_demo_account --reset` with `DATABASE_URL` from
      the existing repo secret (same secret db-backup.yml uses — verify its
      name, don't invent a second one).
- [x] The command already deletes visitor threads/replies, quiz attempts,
      progress, notifications, XP, and stray enrollments, and re-asserts the
      account (`seed_demo_account.py:148-173`, `:106-146`) — no command
      changes expected; if the reset needs anything new, that's a finding to
      record, not silently patch.
- [x] Failure visibility: the workflow must fail loudly (non-zero exit) so
      the repo's Actions tab / notification email surfaces a broken reset.

## Frontend tasks

- [x] `types/index.ts`: add `is_demo: boolean` to the `User` type. [P with
      backend B3 shipping first]
- [x] Demo banner: slim persistent bar when `user.is_demo` — copy along the
      lines of "You're in the shared demo. Progress is visible to other
      visitors and resets nightly." Rendered from the layout so it's on every
      authenticated page. Per UI preferences: readable type, not a whisper.
- [x] Friendly blocked-write handling: central detection of a 403 whose body
      carries `demo_blocked` (axios interceptor in `services/` or the shared
      error helper) → surface "Not available in the demo" instead of a raw
      error. Individual pages don't need bespoke handling.
- [x] Discussions UI: when `user.is_demo`, hide the new-thread/reply
      composers and edit/delete affordances (the backend enforces; the UI
      shouldn't offer dead controls).
- [x] Profile & settings pages: when `user.is_demo`, disable the profile
      form, settings form, and avatar upload/remove controls with a short
      inline note ("Demo account can't be edited") rather than letting the
      user fill a form that 403s on submit.
- [x] `TermsPage.tsx:83-89`: tighten "reset regularly" to "reset nightly" now
      that it's true.
- [x] Vitest: banner renders for `is_demo: true` and not for a normal user;
      discussion composer hidden for demo; profile form disabled for demo.

## Verification

- [ ] `/verify-stack` PASS (backend pytest, `tsc --noEmit` 0 errors, eslint 0
      errors) — frontend checks run in the container (`.npmrc` pins
      `os=linux`; host npm breaks on missing darwin rollup binary).
- [x] Backend test names to exist and pass (indicative, one per enforcement
      point): demo blocked on enrollment-create (both paths), profile PATCH,
      auth/user PUT, settings PATCH, avatar upload, avatar delete,
      gamification avatar PATCH, thread create, reply create, thread/reply
      edit+delete; demo **allowed** on lesson progress, lesson-quiz answer,
      unit-quiz submit, notification read; `demo_blocked` code present in the
      403 body; per-IP demo throttle keying; registration sub-paths 403;
      `is_demo` serializer field.
- [x] All pre-existing demo tests still green (password change, unenroll
      refuse, email suppression, invite invalid-mark) after the B1 refactor.
- [ ] Manual flow (local stack, seeded): click "Try the demo" → banner
      visible on dashboard → complete a lesson section and answer a lesson
      quiz (works) → open a discussion thread (readable, no composer) → open
      profile and settings (forms disabled with note) → attempt avatar upload
      via curl with the demo token (403 `demo_blocked`) → log in as a normal
      student → post a reply, edit profile, upload avatar (all still work).
- [ ] Reset workflow (post-merge): trigger `demo-reset.yml` via `workflow_dispatch` once
      against Neon; confirm it exits 0 and the demo account's visitor data is
      wiped / baseline restored (spot-check: demo login still 200, DEMO101
      enrollment intact, Unit 1 complete).
- [ ] Prod rollout order is boring this phase (no migrations): merge → Render
      deploys → dispatch the reset workflow once → click through the live
      demo banner + one blocked write + one allowed write on stemquests.com.

## Notes

- The `demo_blocked` error code is the contract between B1 and the frontend
  interceptor — pin its exact JSON shape in a backend test before writing the
  frontend detection.
- `@throttle_classes` replaces DRF defaults on `demo_login`
  (`accounts/views.py:33-65`); B4 touches the *global* user throttle, not
  demo-login's scoped one — don't conflate them.
- `seed_demo_account` deletes non-DEMO101 enrollments on every run even
  without `--reset` (`seed_demo_account.py:92-96`) — after B2 blocks
  enrollment creation, that line becomes belt-and-braces, not the only
  defense.

## Outcome (implementation session, 2026-07-27)

Deliberate deviations and findings, in the phase-55 tradition:

- **New GitHub repo secret required before the reset workflow may run:
  `DEMO_ACCOUNT_PASSWORD`** (same value as the Render env var). Discovered
  during B6: `seed_demo_account` re-asserts the demo password from
  `settings.DEMO_ACCOUNT_PASSWORD`, which falls back to the published
  `Admin123!` when unset — an unconfigured nightly run would silently
  un-rotate the production demo password (reverting phase 44). The workflow's
  first step hard-fails with a clear error until the secret exists.
- **`core/demo.py` also grew `is_demo_email(email)`**: the fifth existing
  call site (invite creation) compares a raw request-supplied email string,
  not a user object, so `is_demo_user()` didn't apply. Both helpers share the
  one settings comparison.
- **`/api/auth/user/` is blocked via a `DemoSafeUserDetailsView` shadow**
  (subclass of dj-rest-auth's `UserDetailsView` with
  `NotDemoAccountForWrites`), mounted ahead of the `dj_rest_auth.urls`
  include — the same shadowing pattern as `password/reset/`.
- **The unenroll refusal body changed shape**: `EnrollmentViewSet.destroy`
  now raises the standard `demo_blocked` body instead of its bespoke phase-55
  message, so the frontend interceptor covers it too. The phase-55 test
  asserts only the 403 + row intact, so it still passes unmodified.
- **All demo-policy tests live in one cross-app file**,
  `backend/core/tests/test_demo_lockdown.py` (32 tests: blocked writes with
  the exact-body pin, allowed learning writes, normal-user regression,
  `is_demo` field, throttle keying, registration sub-path stubs), rather than
  scattered per-app — the file states the whole policy in one place.
- **Frontend notes**: there is no separate profile page — profile, settings,
  and avatar all live in `SettingsPage.tsx`, so the "profile & settings
  pages" task is one file. The demo-blocked toast is wired through a
  module-level listener bridge in `services/api.ts` because the axios
  interceptor runs outside React; `ToastContext` registers it. The banner is
  rendered from `Layout.tsx` (and kept in learning mode, where the header is
  hidden).
