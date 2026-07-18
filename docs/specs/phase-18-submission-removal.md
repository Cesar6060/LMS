# Phase 18: Submission Removal

## Goal

Remove the assignment/submission/grading system entirely. The platform focuses on
course content (lessons) and comprehension quizzes; a student's course grade is
computed from exactly two sources: quiz scores and lesson completion
("participation"), with per-course configurable weights that sum to 100. The
`assignments` Django app (Assignment, Submission, SubmissionFile,
SubmissionHistory, Grade models) is deleted along with all endpoints, UI,
notifications, and email hooks tied to it. The instructor gradebook and CSV
export survive, rebuilt as a students × quizzes matrix with a lesson-completion
column and weighted overall grade. All data is dev/seed data — the destructive
migration runs with no export step.

## Decisions made during scoping

- Entire assignments app is removed (not converted to ungraded activities).
- Gradebook + CSV export are kept, rebuilt for quizzes + completion.
- `CourseGradingConfig` is kept with two weights (`quizzes_weight`,
  `participation_weight`); existing rows migrate by folding
  `assignments_weight` into the two remaining weights proportionally (rounding
  so they sum to 100; a config that was 100% assignments becomes 50/50).
- Quizzes have **no due dates** (verified in `quizzes/models.py`), so
  "Upcoming Deadlines" (dashboard) and calendar deadline events are removed —
  they were assignment-only. Calendar keeps `reminder` events.
- Instructor inline quiz quick-grade (`quick_grade_quiz`) survives — it is the
  only manual grading affordance left and powers gradebook cell editing.
- Email preferences `email_grades`, `email_submissions`, `email_due_reminders`
  are removed (all assignment-specific); `email_announcements` stays.
- Notification types `submission`, `grade`, `new_assignment`, `resubmission`
  are removed; existing notification rows of those types are deleted by data
  migration.

## Out of scope

- Adding due dates or availability windows to quizzes.
- Any new grading features (rubrics, curves, extra credit).
- Changes to quiz-taking flow, lesson player, or progress tracking mechanics.
- Discussion forums, announcements, roster (untouched except where they render
  assignment data).
- Instructor Analytics Dashboard (still the next candidate phase after this).

## Backend tasks

Order matters: decouple dependents first, then drop the app.

### Decouple notifications

- [x] `notifications/signals.py`: delete `notify_students_on_new_assignment`,
      `notify_instructor_on_submission`, the Grade post_save handler, and
      `notify_student_resubmission_allowed`; remove the
      `from assignments.models import ...` import (module is loaded at startup
      via `NotificationsConfig.ready()`, so this must land before the app is
      deleted). Keep enrollment/announcement/discussion signals.
- [x] `notifications/models.py`: remove `submission`, `grade`,
      `new_assignment`, `resubmission` from `TYPE_CHOICES`.
- [x] Replace the body of
      `notifications/migrations/0003_rewrite_assignment_urls.py` with a no-op
      (`migrations.Migration` with no operations) and **remove its dependency
      on `('assignments', '0001_initial')`** — otherwise a fresh
      `migrate` breaks once the assignments app is gone. The migration is
      already applied in the dev DB, so keeping the filename preserves history.
- [x] New notifications migration: alter `type` choices + data migration
      deleting notification rows whose type is one of the four removed values.

### Decouple courses

- [x] `courses/models.py` `CourseGradingConfig`: remove `assignments_weight`;
      keep `quizzes_weight` + `participation_weight` with validation that they
      sum to 100. Migration includes a data step redistributing the old
      assignments weight proportionally (50/50 fallback when quizzes and
      participation are both 0).
- [x] `courses/serializers.py:499-508`: grading-config serializer — two weights,
      sum-to-100 validation.
- [x] `courses/views.py` rewrite the assignment-touching functions (runtime
      imports at 484, 507, 556, 993, 1255, 1547, 2511):
  - [x] `gradebook`: students × quizzes matrix (best attempt per quiz),
        completion percentage column, weighted total + letter grade. Drop
        submission status colors (missing/late/submitted); a quiz cell is
        either a score or empty.
  - [x] `gradebook_export` CSV: same columns as new matrix.
  - [x] `student_grade_summary` (my-grades): quizzes + participation only.
  - [x] Instructor dashboard: remove pending-grade counts and
        recent-submissions block.
  - [x] Student dashboard: remove `assignments_due` and upcoming deadlines;
        course progress loses its assignments component.
  - [x] Calendar: remove assignment deadline events (keep reminders).
  - [x] `courses/admin.py:70`: grading-config admin reflects two weights.
- [x] `courses/management/commands/seed_data.py` and
      `populate_csharp_course.py`: drop assignment/submission/grade creation
      (top-level imports break startup of these commands otherwise).

### Decouple accounts + core

- [x] `accounts/models.py`: remove `email_grades`, `email_submissions`,
      `email_due_reminders` from `UserPreferences` (+ migration);
      update `accounts/serializers.py:18`.
- [x] `core/email.py`: delete `notify_student_of_grade` and
      `send_grade_notification`.

### Delete the app

- [x] Run `docker compose exec backend python manage.py migrate assignments zero`
      to drop the five tables and clear `django_migrations` rows **before**
      deleting the code.
- [x] Delete `backend/assignments/` entirely.
- [x] Remove `'assignments'` from `config/settings.py:44` INSTALLED_APPS and
      the include from `config/urls.py:24`.
- [x] Delete any files under `backend/media/submissions/` (currently none
      exist, but check).

### Backend tests

- [x] Delete `assignments/tests.py` (31 tests) with the app.
- [x] `courses/tests.py`: remove/rewrite the gradebook, my-grades, CSV-export,
      and remove-student-preserves-grades tests (~25–30 tests, imports at
      lines 7, 848, 973, 1029). New tests: gradebook matrix shape (quizzes +
      completion + weighted total), CSV export columns, my-grades weighted
      calc, weight-sum validation, config migration default.
- [x] `notifications/tests.py`: remove submission/grade/new-assignment/
      resubmission notification tests and the URL-migration tests (import at
      line 8).
- [x] `config/tests/test_url_conf.py:42`: drop the assignments URL assertion.

## Frontend tasks

### Preserve the quiz quick-grade path first

- [x] Move `quickGradeQuiz` from `services/assignments.ts:181` into
      `services/quizzes.ts`; update `components/gradebook/EditableGradeCell.tsx`
      to import it from there and delete its assignment branch (79-83).

### Delete

- [x] `pages/assignments/AssignmentDetailPage.tsx`,
      `pages/instructor/GradingPage.tsx`,
      `components/manage/AssignmentDialog.tsx`, `services/assignments.ts`.
- [x] Routes in `App.tsx`: `/courses/:code/assignments/:assignmentId` and
      `/instructor/assignments/:assignmentId/grade` (+ imports at 17-19, 27).
      Keep `/courses/:code/grades` and `/instructor/courses/:code/gradebook`.
- [x] Types in `types/index.ts`: `AssignmentListItem`, `Assignment`, `Grade`,
      `SubmissionFile`, `SubmissionHistory`, `Submission`,
      `RecentSubmission`, `UpcomingDeadline`; assignment variants of
      `Notification.type` (line 226); `pending_submissions` on
      `InstructorCourseProgress`; `recent_submissions` on
      `EnhancedDashboardInstructor`; assignment members of `GradebookItem`,
      `StudentGradeItem`, `StudentGradeDetailItem`, `GradeSummary`,
      `CourseProgressItem`, `CalendarEvent`, `GradingConfig`
      (`assignments_weight`); `email_grades`/`email_submissions`/
      `email_due_reminders` on `UserPreferences`. Matching cleanup of
      gradebook types in `services/courses.ts` (84-133).

### Rework mixed views

- [x] `pages/instructor/GradebookPage.tsx`: students × quizzes matrix +
      completion % column + weighted total/letter grade; keep
      `EditableGradeCell` for quiz cells; drop assignment summary columns and
      missing/late legend.
- [x] `pages/student/MyGradesPage.tsx`: quiz summary + participation cards,
      quiz-only grade table.
- [x] `components/course/StudentGradeCard.tsx`: quizzes + participation
      breakdown; `hasAnyGrades` no longer checks assignments.
- [x] `components/course/GradingConfigModal.tsx`: two sliders (quizzes,
      participation) constrained to sum 100.
- [x] `pages/DashboardPage.tsx`: remove Upcoming Deadlines section and
      instructor Pending Submissions list; course progress shows lessons +
      quizzes only.
- [x] `pages/courses/CourseDetailPage.tsx`: remove Assignments section
      (589-646); quizzes section stays.
- [x] `pages/instructor/ManageCoursePage.tsx` +
      `components/manage/OutlineUnitCard.tsx`: remove assignment state,
      handlers, dialog mount, per-assignment rows and "Grade submissions"
      links; Gradebook quick-action link stays.
- [x] Calendar: `WeekCalendar.tsx` and `EventDetailPopup.tsx` lose the
      assignment event type and "View Submissions" action.
- [x] `components/notifications/NotificationBell.tsx`: remove the four
      assignment-related icon cases (104-123).
- [x] `pages/SettingsPage.tsx`: remove grade/submission/due-reminder email
      toggles (303-317); announcements toggle stays.
- [x] `components/layout/Header.tsx`: remove `/assignments` and
      `/instructor/assignments/` breadcrumb cases (98-99, 117); keep Grades
      and Gradebook breadcrumbs.

## Verification

- [x] `grep -ri "assignment\|submission" backend/ frontend/src --include='*.py' --include='*.ts' --include='*.tsx' -l`
      returns only intentional survivors (quiz internals like
      `QuizSubmissionSerializer`/`submitQuiz` naming, if kept) — zero
      references to the assignments app or its endpoints.
- [x] Fresh-database migrate proves the notifications-0003 fix:
      `docker compose run --rm backend python manage.py migrate` against a
      brand-new database completes with the assignments app absent.
- [x] `cd backend && pytest` — full suite passes; no assignment tests remain.
      New tests cover: gradebook matrix (quiz columns, completion column,
      weighted total), CSV export, my-grades weighted calc, grading-config
      sum-to-100 validation and migration redistribution, notification rows of
      removed types purged.
- [x] `cd frontend && npx tsc --noEmit` — 0 errors (proves all dead types and
      imports are gone).
- [x] `cd frontend && npm run lint` — 0 errors.
- [ ] Run `/verify-stack` and show output.
- [ ] Manual click-through (instructor): dashboard (no pending submissions),
      manage course (no assignment rows/dialog), gradebook (quiz columns +
      completion + totals, inline quiz grade edit persists), CSV export
      downloads with new columns, grading-config modal saves 60/40.
- [ ] Manual click-through (student): dashboard (no deadlines section), course
      detail (no assignments section), take/complete a quiz, My Grades shows
      quiz + participation + weighted total consistent with the gradebook,
      settings shows only the announcements email toggle, notification bell
      renders existing notifications without errors.
