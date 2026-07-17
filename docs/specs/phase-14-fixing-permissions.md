# Phase 14: Fixing Permissions

> Note: PLAN.md's "Phase 14" is Instructor Analytics Dashboard. This is a custom phase inserted before it; it does not correspond to a PLAN.md section.

## Goal

Close the real authorization holes found in the backend audit (any authenticated user can create/list Units and Lessons via the bare ViewSets, and can read every course's announcements), then eliminate the permission-check duplication that let those holes happen: one shared permissions module used by all apps, one denial convention (403 + `{'detail': ...}`) applied everywhere including course-scoped list endpoints, and a frontend that renders a shared `<AccessDenied>` state on 403 instead of a generic "Failed to load" string. Instructor browse-all course visibility stays as-is (deliberate product behavior).

## Decisions made (interview)

- **Scope:** backend holes + helper consolidation + denial standardization + frontend ownership/403 UX. All four.
- **Instructor course visibility:** keep as-is — instructors see all courses read-only (writes still blocked by `IsCourseInstructor`).
- **Denial convention:** 403 with `{'detail': ...}` (DRF `PermissionDenied`) everywhere, **including course-scoped list endpoints** (e.g. non-enrolled user on `/api/units/{id}/assignments/` gets 403, not empty 200). Global, user-scoped lists (`/api/courses/`, notifications, reminders) keep queryset filtering. Notifications keep their 404-on-other-user's-object behavior (recipient-scoped lookup; switching to 403 would leak existence).
- **Refactor depth:** shared module, migrate ALL apps — quizzes/discussions/assignments local helpers deleted, ~30 inline checks in `courses/views.py` migrated.
- **403 UX:** shared `<AccessDenied>` component rendered in place (no redirect, URL preserved), with a link back to the dashboard.

## Out of scope

- Instructor Analytics Dashboard (PLAN.md's Phase 14) — separate future phase.
- Restricting instructor browse-all course visibility (`CourseViewSet.get_queryset` stays).
- `reset_lesson_progress` staying instructor-only (by design per docstring; unchanged).
- Accounts app boundary tests (endpoints are self-scoped to `request.user`; low risk).
- New roles (TA, admin), Django Groups, or replacing the `is_instructor` boolean.
- ThreadDetailPage moderation-button flash on load (cosmetic; separate fix).
- Changing non-permission error responses (validation errors etc. keep their current shapes).

## Backend tasks

### 1. Shared permissions module (`backend/courses/permissions.py`)

- [x] Add module-level helpers (single source of truth):
  - `is_course_instructor(user, course)` → `course.instructor == user`
  - `is_enrolled(user, course)` → `Enrollment.objects.filter(user=user, course=course, is_active=True).exists()`
  - `can_access_course(user, course)` → instructor or enrolled
  - `require_course_instructor(user, course)` / `require_course_access(user, course)` → raise `rest_framework.exceptions.PermissionDenied` with a clear detail message (used by function-based views and generics)
- [x] Give `IsCourseInstructor` and `IsEnrolledOrInstructor` a `has_permission` implementation (currently object-level only — this is the root cause of the ViewSet holes). Create/list on ViewSets using them must no longer fall through to bare `IsAuthenticated`.

### 2. Fix the security holes (`backend/courses/views.py`)

- [x] `UnitViewSet` (`views.py:143`) — `POST /api/units/`: reject unless `request.user` is the target course's instructor (403). `GET /api/units/` list: scope queryset to units of courses the user teaches or is actively enrolled in (currently `Unit.objects.all()` at `:146`).
- [x] `LessonViewSet` (`views.py:238`) — same fix: create requires ownership of `unit.course`; list queryset scoped (currently `Lesson.objects.all()` at `:240`).
- [x] `AnnouncementViewSet` (`views.py:784`) — `GET /api/announcements/` list and retrieve: scope queryset to courses the user teaches or is enrolled in (currently `Announcement.objects.all()` at `:786`).

### 3. Migrate all apps to the shared module

- [x] `quizzes/views.py` — delete local `is_course_instructor` (`:17`) and `is_enrolled` (`:22`); import from `courses.permissions`. Keep function-based `@api_view` style.
- [x] `discussions/views.py` — delete local `is_course_instructor` (`:18`), `is_enrolled` (`:23`), `can_access` (`:28`); import from `courses.permissions`. Author-ownership checks (edit=author, delete=author-or-instructor, locked-thread gate) stay local — they're discussion-specific.
- [x] `assignments/views.py` — delete local `is_enrolled_or_instructor` (`:24`); import `can_access_course`/`require_*`.
- [x] `courses/views.py` — replace the ~30 inline `if course.instructor != request.user` checks and inline `Enrollment.objects.filter(...)` checks with the shared helpers (sites listed in audit: `:115, :222, :313, :369, :396, :800, :808, :821, :847, :862, :957, :1221, :1334, :1357, :1383, :1471, :1482, :1528`, lesson-questions `:1771-2077`, attachments `:2206-2303`, sections `:2334-2444`, `:2503, :2586`). Move the ~12 inline `from rest_framework.exceptions import PermissionDenied` imports to module top.

### 4. Standardize denial responses

- [x] All permission denials → 403 with `{'detail': ...}` (raise `PermissionDenied`). Replace `{'error': ...}` bodies in courses/assignments **for permission denials only**.
- [x] Course-scoped list endpoints that currently return `.none()` (empty 200) for unauthorized users now 403: `UnitAssignmentListCreateView` (`assignments/views.py:68`), `AssignmentSubmissionsView` (`:315`), and any equivalent in courses. `AssignmentListView` (`:40`) stays filtered if it's a cross-course "my assignments" list — confirm its semantics before changing.
- [x] `update_course_activity` (`courses/views.py:1456`) — 404 `not_enrolled` → 403.
- [x] Keep: notifications 404-for-non-recipient; global user-scoped list filtering (`/api/courses/`, `InstructorReminderViewSet`, notifications).

### 5. Tests

- [x] New hole-closing tests (courses): student `POST /api/units/` → 403; student `POST /api/lessons/` → 403; `GET /api/units/`, `/api/lessons/` list only returns own/enrolled courses' objects; non-enrolled `GET /api/announcements/` doesn't include other courses' announcements; announcement retrieve for non-enrolled course → 403/404-consistent with queryset scoping.
- [x] Quizzes gaps: `question_detail` as student → 403; `quick_grade_quiz` as student and as non-owner instructor → 403.
- [x] Update existing tests that assert empty-200 lists for unauthorized users (e.g. `assignments/tests.py:130` `test_list_assignments_not_enrolled`, `:256 test_student_cannot_list_submissions`) to expect 403 where the endpoint changed.
- [x] Cross-instructor tests: instructor B (owns nothing here) hits instructor A's gradebook/roster/quiz-editor endpoints → 403 (verify existing coverage, add where missing).
- [x] All permission-denial assertions check `response.data['detail']` exists (locks in the body convention).

## Frontend tasks

- [x] `src/components/AccessDenied.tsx` — shared component: "You don't have access to this" + link to `/dashboard`. Rendered in place of page content.
- [x] `src/services/api.ts` — export `isForbidden(error): boolean` helper (axios error with status 403).
- [x] Instructor pages render `<AccessDenied>` on 403 instead of generic error text: `GradebookPage`, `GradingPage`, `QuizEditorPage`, `StudentRosterPage`, `ManageCoursePage` (also remove its post-fetch `navigate('/courses')` at `:141-142` in favor of `<AccessDenied>`).
- [x] Student-facing course pages render `<AccessDenied>` on 403 (new possibility now that course-scoped lists 403): `AnnouncementsPage`, `DiscussionsPage`, `ThreadDetailPage`, `MyGradesPage`, assignment/quiz detail pages.
- [x] `CourseDetailPage` — verify course-scoped list fetches (announcements, discussions, assignments) only fire when `canAccessContent`; the catalog view for non-enrolled students must not surface 403 errors.
- [x] Remove redundant in-component role check in `CreateCoursePage.tsx:23` (already wrapped in `InstructorRoute`).
- [x] Naming cleanup — local `isInstructor` renamed to what it actually checks: `isCourseOwner` (CourseDetailPage, CoursePlayerPage, LessonPage, AnnouncementsPage, ThreadDetailPage, ManageCoursePage), `isAuthor` (`AnnouncementDetailPage.tsx:43`). Global-flag uses (`user?.is_instructor`) unchanged.
- [x] Types: no model changes expected; confirm no new fields needed in `types/index.ts`.

## Verification

- [x] `docker compose exec backend pytest` — all green, including every new test above (was 186 passing; count must go up, not down).
- [x] `docker compose exec frontend npx tsc --noEmit` — 0 errors.
- [x] `docker compose exec frontend npm run lint` — 0 errors.
- [x] `/verify-stack` output shown as evidence.
- [x] Manual API checks (curl or DRF browsable, student token): `POST /api/units/` with another course's id → 403 `{'detail': ...}`; `GET /api/lessons/` → only own courses' lessons; `GET /api/announcements/` → only enrolled courses' announcements.
- [ ] Manual UI flow: (1) log in as instructor B, paste instructor A's `/instructor/courses/{code}/gradebook` URL → AccessDenied component, no redirect; (2) log in as non-enrolled student, open a course's `/discussions` URL → AccessDenied; (3) enrolled student's normal course flow (lessons, assignments, discussions) unchanged.
- [ ] Existing behavior preserved: instructors still see all courses in the catalog list.
