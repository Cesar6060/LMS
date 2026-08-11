---
paths:
  - "backend/**/views.py"
  - "backend/**/permissions.py"
  - "backend/**/urls.py"
---

# Backend Views: Authorization, Throttling, Demo, Uploads

## Authorization — never inline; import from `courses/permissions.py`
Predicates (bool): `is_course_instructor` (:10) `course.instructor == user`;
`is_enrolled` (:15) active `Enrollment`; `can_access_course` (:21) either — read access.

Guards (raise `PermissionDenied` → 403 `{'detail': ...}`):
- `require_course_instructor` (:26) — instructor-only writes/management.
- `require_course_access` (:32) — enrolled-or-instructor content reads.
- `require_enrollment` (:38) — student-only variant of `require_course_access` (instructor
  refused too), for writes only a learner performs (`quizzes/views.py:340`).
- `require_pending_invite` (:50) — code-based joins need a pending `CourseInvite` for the
  user's own address; the class code is only a second factor. Matches the lowercased email
  **exactly, never `iexact`**: Postgres `UPPER()` folds Turkish dotless i (U+0131) onto
  ASCII `i`, handing one student another's enrollment (`courses/views.py:146`).
- `require_unit_unlocked(user, unit)` (:83) — enforce locking at **every content read**,
  not just in the UI; the instructor still sees their own. 19 call sites (12
  `courses/views.py`, 7 `quizzes/views.py`); a new lesson/quiz read endpoint adds one.

Scoping (no raise): `locked_unit_ids_for(user, course)` (:97) strips locked units out of
progress denominators and flat content lists (`quizzes/views.py:555`);
`accessible_course_ids(user)` (:108) scopes ViewSet querysets (`courses/views.py:229`).

Four DRF `BasePermission` classes are here too — `IsInstructor` (:118),
`IsInstructorOrReadOnly` (:128), `IsCourseInstructor` (:139), `IsEnrolledOrInstructor`
(:174). A class beats a call on ViewSets/`APIView`: declarative, and per-object checks.

## Throttling
- Never use stock DRF throttle classes. `core/throttling.py` overrides `get_ident`
  (Cloudflare's `CF-Connecting-IP`; the rotating edge IP in `X-Forwarded-For` gives every
  request a fresh bucket) and the cache alias (the default LocMemCache is per-worker, so
  each gunicorn worker enforced its own copy of every rate).
- Naming any throttle on a view **replaces** `DEFAULT_THROTTLE_CLASSES`. Spread
  `*GLOBAL_THROTTLES` (`core/throttling.py:145`) alongside the scoped class
  (`accounts/views.py:41, 93, 106, 123`). Pinned by `accounts/tests.py:883-905`
  (`test_scoped_views_keep_the_global_ceilings`).
- On `@api_view` function views the scope goes on the generated class:
  `lesson_attachments.cls.throttle_scope = 'attachment_upload'` (`courses/views.py:3157`;
  also 1985, 2063, 2235, 2373, 3523, `accounts/views.py:71`). Omit it and the throttle is
  **silently inert**.
- `ClientIPScopedWriteRateThrottle` (`core/throttling.py:148`) exempts GET/HEAD/OPTIONS —
  use when a throttled write shares a view with reads that must stay unthrottled
  (`courses/views.py:1909, 3032, 3401`).
- Every new scope needs a non-`None` default in `DEFAULT_THROTTLE_RATES`
  (`config/settings.py:313`); `None` is unlimited, so a missing Render env var must fail
  safe, not silently open. Sweep tests: `courses/tests.py:3803`, `:3828`.
- Any dj-rest-auth view you shadow must be mounted with `re_path(r'^…/?$')` **before**
  `include('dj_rest_auth.urls')` — the package uses optional-slash regexes, so a `path()`
  shadow catches only the trailing-slash spelling and the bare URL falls through to the
  unthrottled original (`accounts/urls.py:36, 43, 50, 56, 60`).

## Demo write-blocking
- `core/demo.py` is the single source of truth; never compare emails inline.
- Function views: `require_not_demo(user)` at the write branch (~20 call sites in courses/
  accounts/discussions/gamification); `require_not_demo_course(course)` for writes aimed
  at the demo course (`courses/views.py:2048, 2092, 2122, 2159, 2213`).
- Class-based views: `NotDemoAccountForWrites` from `core/permissions.py`
  (`accounts/views.py:82`); it raises rather than returning False, to keep the body shape.
- Denials must carry `DEMO_BLOCKED_BODY` verbatim (`core/demo.py:19`) — 403 with
  `code: 'demo_blocked'`; the frontend axios interceptor keys on that exact string
  (`frontend/src/services/api.ts:77`).
- Learning writes (lesson progress, quiz attempts, notification read-marks) stay open to
  the demo account; identity and shared-surface writes (profile, settings, avatars,
  enrollments, discussion posts) are blocked (`core/demo.py:85`).

## Uploads
Mandatory order, no step skipped: size limit from a settings constant
(`ATTACHMENT_MAX_REQUEST_BYTES` / `ATTACHMENT_MAX_UPLOAD_BYTES` / `AVATAR_MAX_UPLOAD_BYTES`)
→ extension allowlist → `verify_upload(f, ext)` (or `verify_image` on image-only paths)
from `core/uploads.py` → store (`courses/views.py:3094-3133`, `accounts/views.py:199-243`).
Extension and size are client-supplied strings; the byte check stops a disguised payload.
Serve via `download_url(field, filename)` (`core/uploads.py:258`), which pins disposition
and content type onto the presigned URL — never `field.url`.
