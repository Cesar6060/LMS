---
paths:
  - "backend/**/*.py"
---

# Django Backend — always-on core

The short list that applies to every Python file. The heavy conventions are
split by path: `backend-views.md` (permissions, throttling, demo guards,
uploads), `backend-serializers.md`, `backend-tests.md`, `backend-migrations.md`.

## Shape

- PEP 8; type hints where they earn their place. Settings module is
  `config.settings` — there is no `gamedev_platform` package.
- Everything is mounted under `/api/` (`backend/config/urls.py:27-38`):
  `api/auth/` → accounts, `api/courses/` → courses, `api/notifications/`,
  `api/gamification/`, and quizzes + discussions mounted at bare `api/`.
- **The doubled prefix is real.** `courses/urls.py:6` registers a router at
  `courses`, under a root include already at `api/courses/`, so the canonical
  course URL is `/api/courses/courses/{code}/`. It is not a typo — do not
  "fix" it, and do not guess the single-segment spelling when writing a client
  or a test.
- Course-scoped routes key on the course **code** (`DEMO101`), not the pk.

## Authorization

- Never compare the caller to the course owner inline. Every
  authorization decision imports a helper from `courses/permissions.py` — ten
  functions plus four DRF permission classes. See `backend-views.md`.
- Denials are always `raise PermissionDenied(...)` → **403** with a
  `{'detail': ...}` body. Never an empty list, never `{'error': ...}`, never a
  200 with the data quietly removed.

## Shared services in `core/`

`core/` is not an installed app — it is a plain package of mandatory
call-throughs. Do not reimplement any of these locally:

- `core.email.send_templated_email(subject, template_name, context,
  recipient_list, triggered_by=...)` — always pass `triggered_by`. It is what
  refuses outbound mail caused by the demo account (`core/email.py:113`), and
  it is also how the HTML/text pair and the transactional headers get built.
- `core.demo` — demo write-blocking. `core.uploads` — file verification and
  `download_url()`. `core.throttling` — every throttle class.
  `core.password_validation` — HIBP screening. `core.pagination` — the
  per-view page classes.
- There is **no** global `DEFAULT_PAGINATION_CLASS`. A list endpoint that
  needs paging names one explicitly (`NotificationPagination`,
  `RosterPagination`); everything else returns a full list on purpose.

## XP and badges

Award XP only through `gamification.services` helpers —
`award_lesson_completion`, `award_quiz_pass`, `award_lesson_quiz_pass`. They
own idempotency (a source key per award), streaks and badge evaluation.
Writing to the profile or XP rows directly desynchronises all three.

## Shell quirk

Bare `head` on this machine is shadowed by an unrelated Perl tool. Use
`/usr/bin/head` in any command you run.
