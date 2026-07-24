# Phase 15: Routing Audit

Custom phase (not from PLAN.md). Branch: `fix/routing-audit` off `lms/main`.

## Goal

Audit found three confirmed 404 bugs and several routing-behavior gaps. This phase fixes the broken links/paths (a dead "Back to Courses" link, notification URLs pointing at a nonexistent `/assignments/:id` route, a doubled-segment API path in the quiz quick-grade call), and closes the behavior gaps: deep links now survive login, non-instructors hitting `/instructor/*` see the AccessDenied card instead of a silent redirect, `/verify-email` is consistent with the other auth pages, and the legacy `LessonPage` route becomes a redirect into the course player. The backend URL layout (doubled prefixes, bare-`/api/` mounts for quizzes/discussions) is intentionally **not** restructured; instead it gets regression tests and documentation so the fall-through ordering can't silently break.

## Out of scope

- Restructuring backend URL paths (`/api/courses/courses/`, `/api/assignments/assignments/:pk/`, bare-`/api/` mounts stay as-is — guard tests only).
- Adding a frontend test runner (no vitest/jest exists; frontend verification is tsc + lint + manual click-through).
- Route param format validation in components (bad ids keep rendering in-page error cards — current behavior is acceptable).
- `EventDetailPopup.tsx:180` external `event.url` redirect hardening.
- Breadcrumb changes (`Header.tsx` regex crumbs — no broken targets found).
- Any permission logic changes (phase 14 territory; this phase only changes *where users land*, not *what they may access*).

## Backend tasks

- [x] **Fix notification signal URLs** in `backend/notifications/signals.py` — three sites generate `/assignments/{id}`, which matches no frontend route:
  - `new_assignment` (~line 67), `grade` (~line 116), `resubmission` (~line 133) → change to `/courses/{assignment.course.code}/assignments/{assignment.id}` (for `new_assignment`, the course is `instance.unit.course`).
  - Also update the lesson notification (~line 38) from `/courses/{code}/lessons/{id}` to `/courses/{code}/learn/{id}` (the old URL keeps working via the frontend redirect below, but new notifications should use the canonical path).
  - Leave `/instructor/assignments/{id}/grade` URLs (~lines 88/99) untouched — they are valid, and the submission-dedup query at ~line 88 matches on that exact string.
- [x] **Data migration** in `notifications` app: rewrite existing rows where `related_url` matches `^/assignments/(\d+)$` to the course-nested URL, resolving the course code via `apps.get_model('assignments', 'Assignment')`. Rows whose assignment no longer exists: set `related_url` to `''`. Reverse migration: no-op. (Old `/courses/:code/lessons/:id` rows need no rewrite — the frontend redirect keeps them working.)
- [x] **URL guard tests** (new `backend/config/tests/test_url_conf.py` or similar pytest module) asserting via `resolve()`/client that:
  - `/api/courses/{code}/quizzes/` resolves to the quizzes app view and `/api/courses/{code}/threads/` to the discussions app view (the bare-`/api/` fall-through routes, `config/urls.py:18-19`).
  - `/api/quizzes/{id}/quick-grade/{student_id}/` resolves (single `quizzes` segment) and `/api/quizzes/quizzes/{id}/quick-grade/{student_id}/` does **not**.
  - Canonical doubled-prefix paths still resolve: `/api/courses/courses/`, `/api/courses/courses/{code}/`, `/api/assignments/assignments/{pk}/`.
- [x] **Signal URL tests**: notification created for a new assignment / grade / resubmission has a `related_url` of the form `/courses/{code}/assignments/{id}`.
- [x] **Comment in `backend/config/urls.py`** documenting the ordering dependency: `api/courses/` include is evaluated before the bare `api/` includes, so quizzes'/discussions' `courses/{code}/...` routes only resolve because the courses app defines no competing pattern — future courses routes starting with `courses/{code}/quizzes|threads/` would shadow them.

## Frontend tasks

- [x] **Fix quick-grade API path** in `frontend/src/services/assignments.ts:187`: `/quizzes/quizzes/${quizId}/quick-grade/${studentId}/` → `/quizzes/${quizId}/quick-grade/${studentId}/` (matches `quizzes/urls.py:21`; sibling `quizzes.ts` already uses single-segment paths).
- [x] **Fix dead link** in `frontend/src/pages/instructor/GradingPage.tsx:167`: `<Link to="/instructor/courses">` targets no route (lands on 404). Change to `/dashboard` (instructor courses live on the dashboard) and relabel "Back to Dashboard".
- [x] **Preserve deep links through login** (`frontend/src/App.tsx`, `LoginPage.tsx`, `services/api.ts`):
  - `ProtectedRoute` and `InstructorRoute`'s unauthenticated branch: `<Navigate to="/login" state={{ from: location }} replace />`.
  - `LoginPage.tsx:26`: after login, `navigate(location.state?.from?.pathname ?? nextParam ?? '/dashboard', { replace: true })`.
  - `api.ts:33` 401 interceptor (full-page redirect, router state is lost): redirect to `/login?next=${encodeURIComponent(location.pathname + location.search)}`; `LoginPage` reads the `next` query param as fallback. Only accept relative paths starting with `/` (reject `//` and absolute URLs) to avoid open redirects.
  - `PublicRoute`'s authenticated bounce and `RegisterPage` post-register navigation stay `/dashboard`.
- [x] **AccessDenied for non-instructors** (`App.tsx` `InstructorRoute`, ~line 87): replace `<Navigate to="/dashboard" />` with rendering the existing `components/AccessDenied.tsx` card in place — URL preserved, matching the phase-14 in-page 403 pattern. Unauthenticated users still go to `/login` (with `from` state, above).
- [x] **`/verify-email` consistency** (`App.tsx:155-158`): wrap so that an authenticated user with **no verification key in the URL** is redirected to `/dashboard`, but a URL carrying a key still renders `VerifyEmailPage` even when authenticated (email verification is `optional` + `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION=True`, so logged-in users legitimately open verify links). Plain `PublicRoute` is NOT sufficient — it would eat the key. Check how `VerifyEmailPage` receives the key (query param vs path) and gate on that.
- [x] **Retire `LessonPage` route** (`App.tsx:187-194`): `/courses/:code/lessons/:lessonId` becomes a redirect to `/courses/:code/learn/:lessonId` (small wrapper component using `useParams` + `<Navigate replace>`). Update the inbound link at `CourseDetailPage.tsx:553` to point at `/learn/` directly. Delete `pages/LessonPage.tsx` if nothing else imports it (verify with grep first).

## Verification

- [x] `cd backend && pytest` — all pass (206 pre-existing + new URL-guard, signal-URL, and migration tests).
- [x] Data migration check: seed a notification with `related_url='/assignments/<real id>'`, run migration, confirm rewrite; one with a nonexistent assignment id → `''`.
- [x] `cd frontend && npx tsc --noEmit` — 0 errors; `npm run lint` — 0 errors (28 pre-existing exhaustive-deps warnings allowed).
- [x] `/verify-stack` green before anything is marked complete.
- [x] Manual click-through (playwright-core + installed Chrome, `channel: 'chrome'`, demo accounts `instructor@demo.com` / `instructor2@demo.com` / `student1@demo.com`, password `Admin123!`):
  1. Logged out, open `/courses/CS101/discussions` → redirected to `/login` → log in as student1 → land back on `/courses/CS101/discussions` (not `/dashboard`).
  2. As student1, open `/instructor/courses/CS101/gradebook` → AccessDenied card, URL preserved (no dashboard redirect).
  3. Open `/courses/CS101/lessons/<id>` → redirected to `/courses/CS101/learn/<id>`, player renders.
  4. Trigger a new-assignment notification (create assignment as instructor), click it as student → lands on `/courses/:code/assignments/:id` detail page.
  5. As instructor, quiz quick-grade action → network tab shows `/api/quizzes/<id>/quick-grade/<sid>/` returning 200 (not 404).
  6. Logged in, visit `/login` → bounced to `/dashboard`; visit `/verify-email` (no key) → bounced to `/dashboard`.
  7. `/definitely-not-a-route` → NotFoundPage renders.
