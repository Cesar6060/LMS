# Handoff: Phase 15 Routing Audit — implemented, awaiting PR

## Current state
Phase 15 (routing audit) is fully implemented and committed as 4591512 on
`fix/routing-audit` (off `lms/main`). **Not pushed, no PR yet.**
- Backend: `notifications/signals.py` (assignment/grade/resubmission URLs now
  `/courses/{code}/assignments/{id}`, lessons use `/learn/`),
  `notifications/migrations/0003_rewrite_assignment_urls.py` (data migration,
  verified against dev DB), `config/tests/test_url_conf.py` (URL fall-through
  guards), `config/urls.py` (ordering comment), `notifications/tests.py`
  (+7 related_url/migration tests).
- Frontend: `services/assignments.ts` (single-segment quick-grade path),
  `pages/instructor/GradingPage.tsx` (dead link → /dashboard), `App.tsx`
  (guards pass `from` state; InstructorRoute renders AccessDenied in place;
  VerifyEmailRoute; LegacyLessonRedirect), `pages/auth/LoginPage.tsx`
  (restores `from`/`?next=`, sanitized), `services/api.ts` (401 → `?next=`),
  `pages/courses/CourseDetailPage.tsx` (links to `/learn/`);
  `pages/courses/LessonPage.tsx` deleted.
- Verified: pytest **218 passed**, tsc **0 errors**, lint **0 errors**
  (27 pre-existing warnings). Manual click-through **7/7** spec scenarios
  passed (playwright-core + Chrome). Spec checklist fully checked.

## In progress / not done
- Nothing half-finished. Only remaining: push branch and open PR to `lms/main`.

## Next steps
1. `git push -u lms fix/routing-audit` and open a PR to `lms/main` (gh CLI),
   then merge and sync local `main`.
2. Next phase candidate (deferred twice): PLAN.md ~line 1485 "Instructor
   Analytics Dashboard" — user must run `/start-phase` to spec it.

## Decisions made
- InstructorRoute renders `<AccessDenied message="This page is only available
  to instructors." />` in place (phase-14 in-page 403 pattern) — URL preserved.
- Login restore priority: router `from` state, then `?next=` param, else
  `/dashboard`; both validated with startsWith('/') && !startsWith('//') to
  block open redirects.
- 401 interceptor skips the redirect when already on `/login` (avoids reload
  loop / `next=/login`).
- Legacy `/courses/:code/lessons/:id` route is NOT wrapped in ProtectedRoute —
  it redirects to `/learn/…`, which is protected and captures `from` itself.
- Data migration tests call `rewrite_assignment_urls(django_apps, None)`
  directly via importlib (module name starts with a digit).

## Gotchas discovered
- Courses-app nested routes carry the doubled prefix too:
  units list is `/api/courses/courses/{code}/units/`, gradebook is
  `/api/courses/courses/{code}/gradebook/` (cost a failed click-through run).
- Quizzes exist only in VGD101 (ids 1-3); CS101/ROB201 have none — quiz
  quick-grade testing must use VGD101.
- Gradebook `EditableGradeCell` cancels silently if the entered value equals
  the current one — automated grading probes must enter a *different* value.
- No pytest on host: run `docker compose exec backend pytest`.

## Files to read first
- docs/specs/phase-15-routing-audit.md (all items checked — scope + rationale)
- frontend/src/App.tsx (all route guards live here)
- backend/config/urls.py (ordering-dependency comment)
- backend/notifications/signals.py (canonical notification URL formats)
