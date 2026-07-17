# Handoff: Phase 14 Fixing Permissions (implemented, PR open)

## Current state
Phase 14 — Fixing Permissions is **implemented and verified**; spec `docs/specs/phase-14-fixing-permissions.md` is fully checked off except the manual UI click-through.
- Backend: `courses/permissions.py` is now the single source of truth (helpers `is_course_instructor`/`is_enrolled`/`can_access_course`/`require_*`/`accessible_course_ids`; `IsCourseInstructor`/`IsEnrolledOrInstructor` got `has_permission` + owner-only writes). Holes closed: bare `/api/courses/units/` + `/lessons/` create/list, `/api/courses/announcements/` read leak. All apps (`courses`, `assignments`, `quizzes`, `discussions` views.py) migrated off local helpers/inline checks. All denials are 403 + `{'detail': ...}`; course-scoped lists 403 instead of empty 200; `update_course_activity` 404→403. Retrieves keep full querysets so object checks 403 (not 404).
- Frontend: new `src/components/AccessDenied.tsx`, `isForbidden()` in `services/api.ts`, 403 pattern applied to 11 pages (instructor: Gradebook/Grading/QuizEditor/StudentRoster/ManageCourse; student: Announcements/Discussions/ThreadDetail/MyGrades/AssignmentDetail/QuizDetail). `ManageCoursePage` renders AccessDenied instead of `navigate('/courses')`; `CreateCoursePage` redundant role check removed; `isInstructor` locals renamed `isCourseOwner`/`isAuthor`.
- Also updated `.claude/rules/backend.md` standard pattern to the new convention.
- **Verified (all green):** pytest **206 passed** (was 186; 20 new boundary tests) · `tsc --noEmit` 0 errors · `npm run lint` 0 errors (28 pre-existing exhaustive-deps warnings). Live API probes: cross-instructor gradebook/roster/unit-PATCH → 403 detail; non-enrolled student lesson/discussions → 403; bare lists scoped.
- **Git:** branch `feat/phase-14-permissions` (off `lms/main`) → **PR #3** github.com/Cesar6060/LMS/pull/3. Includes the phase-14 spec + previously-untracked phase-13 handoff.

## In progress / not done
- Manual UI click-through (last unchecked spec item): instructor B → other instructor's `/instructor/courses/{code}/gradebook` should show AccessDenied; non-enrolled student → `/courses/{code}/discussions` same; enrolled-student flow unchanged. API layer is test-covered; only the browser rendering is unverified.
- `seed_data` still never run against dev DB (demo accounts from README don't exist until you run it).

## Next steps
1. Click through the manual UI flows above (login via http://localhost:5173/login), then check off the last spec item.
2. Review + merge PR #3.
3. Next phase: PLAN.md "Phase 14: Instructor Analytics Dashboard" (yes, the number collides with this custom phase — spec should be named phase-15 or analytics to avoid clashing with `docs/specs/phase-14-fixing-permissions.md`). Use `/start-phase`.

## Decisions made
- 403 + `{'detail': ...}` for ALL permission denials incl. course-scoped lists (user-chosen); global user-scoped lists (`/api/courses/`, reminders, notifications) keep queryset filtering; notifications keep recipient-scoped 404 (403 would leak existence).
- ViewSet querysets scoped only for `list`; detail actions keep full queryset so object permissions return 403 not 404 (keeps the convention AND `test_get_lesson_detail_not_enrolled`).
- Bare ViewSet create (`/units/`, `/lessons/`) returns 403 pointing to nested endpoints — the create serializers never exposed `course`/`unit`, so bare create was always broken (500); nested routes are the only create path.
- `IsEnrolledOrInstructor` object writes tightened to owner-only (enrolled students previously passed for lesson/unit writes — undocumented hole).
- Instructor browse-all catalog kept as-is (user-chosen product behavior).
- AccessDenied rendered in place (no redirect) so the URL is preserved for debugging.

## Gotchas discovered
- quizzes app mounts at `/api/` not `/api/quizzes/` — question detail is `/api/questions/{id}/` (cost one test-fix cycle).
- Announcement/Unit/Lesson create serializers don't expose their parent FK; bare ViewSet POSTs were 500s, not silent cross-course writes (audit overstated that part).
- Broken `head` shell alias still present — use `sed -n`/grep/tail.
- Stack runs in Docker: pytest/tsc/lint via `docker compose exec -T {backend,frontend} ...`.

## Files to read first
- `docs/specs/phase-14-fixing-permissions.md` (what was decided and shipped)
- `backend/courses/permissions.py` (the new single source of truth)
- `backend/courses/tests.py` — `TestPermissionBoundaries` (the new boundary suite)
- `frontend/src/components/AccessDenied.tsx` + `frontend/src/services/api.ts` (403 UX pattern)
- `PLAN.md` Phase 14 section (~line 1485) if starting the analytics phase
