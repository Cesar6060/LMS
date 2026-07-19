# Phase 21: Instructor Analytics Dashboard

**Status: DEFERRED (2026-07-18).** Scoped but not started — the user judged
analytics not necessary yet and prioritized navigation/button usability
(phase 22) instead. This spec stays as the ready-to-go plan if/when
analytics comes back onto the roadmap. The open questions below are still
open.

## Goal

Give the instructor a per-course view of how the class is actually doing:
overview stats, which quizzes students are struggling with, which students
are falling behind, and an activity trend — so problems can be caught while
there's still time to act, not just at grading time.

This is `PLAN.md`'s "Phase 14: Instructor Analytics Dashboard," carried
forward as the last unbuilt item on the original roadmap (Phase 13
Discussion Forums has since shipped despite PLAN.md's stale "Pending"
label). It's renumbered 21 here to follow the sequential `docs/specs/`
history rather than PLAN.md's original numbering, matching how phases
13(fixing-permissions)/15(routing-audit)/etc. already diverged from PLAN.md.

## Context: rescoped for the post-assignments platform

The original PLAN.md draft (written before Phase 18) specified "assignment
performance" stats and "submissions over time." Phase 18 deleted the entire
`assignments` app — the platform now grades only via quizzes + lesson
completion ("participation"). This spec replaces every assignment-shaped
metric with its quiz/completion equivalent:

| Original (PLAN.md) | Rescoped |
|---|---|
| Assignment performance table | Quiz performance table (avg score, pass rate, completion rate) |
| Submissions over time | Lesson completions + quiz attempts per day |
| — | Everything else (overview, at-risk students) carries over unchanged |

## Decisions made during scoping

- Data sources only: `QuizAttempt` (score, passed, completed_at),
  `LessonProgress` (completed, completed_at), `Enrollment`
  (last_activity_at, is_active). No assignments/submissions data exists.
- Per-course only (like gradebook/roster today), not an aggregate across all
  of an instructor's courses. Instructors here teach a small number of
  courses; a cross-course rollup isn't worth the complexity yet.
- "At-risk" reuses the exact definition already in
  `StudentRosterSerializer.get_is_inactive` (7+ days since last activity) OR
  progress < 50% — no new scoring model, just the two thresholds PLAN.md's
  success criteria already named.
- New instructor-only endpoints under `/api/courses/{code}/analytics/...`,
  following the existing gradebook/roster pattern
  (`require_course_instructor` from `courses/permissions.py`).
- New frontend page at `/instructor/courses/:code/analytics`, linked from
  `ManageCoursePage`'s quick-actions row next to Gradebook/Students/Quizzes.
- Adds `recharts` as a new frontend dependency (not currently installed),
  scoped to the one activity-trend chart — not a platform-wide charting
  adoption.
- Reuse existing UI conventions rather than inventing new ones: dashboard
  stat cards for the overview, gradebook-style tables for quiz/student
  lists, the Phase 20 icon+CTA `EmptyState` pattern for zero-quiz/
  zero-student courses.

## Open questions for you before I start building

1. **`recharts` as a new dependency** — okay to add, or would you rather I
   build a lightweight custom bar/line chart (no new dependency, less
   flexible, matches the hand-rolled progress-bar style already in the
   app)?
2. **Scope for v1** — the four data views below, or do you want me to drop
   the activity-trend chart (the most "nice to have" of the four) to ship
   overview + quiz performance + at-risk students first?

## Out of scope (this phase)

- Cross-course aggregate view across all of an instructor's courses.
- Historical range beyond 30 days, CSV export of analytics data,
  question-level item analysis within a quiz.
- Predictive/ML-based risk scoring — simple threshold rules only.
- Editing grades from this page (gradebook already owns that; analytics is
  read-only).

## API endpoints

```
GET /api/courses/{code}/analytics/overview/    # class-level key metrics
GET /api/courses/{code}/analytics/quizzes/     # per-quiz avg score, pass rate, completion
GET /api/courses/{code}/analytics/students/    # per-student progress/grade/activity, at-risk flag
GET /api/courses/{code}/analytics/activity/    # lessons completed + quiz attempts per day, last 30 days
```

## Backend tasks

### `backend/courses/views.py`

- [ ] `analytics_overview(request, course_code)`: `require_course_instructor`;
      returns `student_count` (active enrollments), `avg_progress_percentage`
      (mean of per-student lesson-completion %), `avg_grade_percentage` (mean
      of per-student weighted grade, reusing `calculate_weighted_grade`),
      `active_last_7_days` count.
- [ ] `analytics_quizzes(request, course_code)`: per quiz in the course —
      `avg_score`, `pass_rate` (passed attempts / total attempts), and
      `completion_rate` (students with ≥1 attempt / active enrollment
      count); ordered ascending by `avg_score` so struggling quizzes surface
      first.
- [ ] `analytics_students(request, course_code)`: per active enrollment —
      `progress_percentage` (reuse the same calc as
      `StudentRosterSerializer.get_progress_percentage`), `quiz_average`,
      `weighted_grade`, `last_activity_at`, `at_risk` (progress < 50 OR
      inactive 7+ days).
- [ ] `analytics_activity(request, course_code)`: last 30 days, grouped by
      date — `lessons_completed` (from `LessonProgress.completed_at`) and
      `quiz_attempts` (from `QuizAttempt.completed_at`); zero-fill days with
      no activity so the frontend doesn't have to.
- [ ] Edge cases: zero enrolled students, zero quizzes — return zeroed/empty
      structures, not errors.

### `backend/courses/urls.py`

- [ ] Add the four paths above, colocated with the existing
      gradebook/roster routes.

### Tests (`backend/courses/tests.py`)

- [ ] Permission boundary per endpoint: instructor of the course (200),
      instructor of a different course (403), enrolled student (403),
      anonymous (401/403) — matches the existing gradebook/roster test
      pattern.
- [ ] Correctness against seeded fixtures: overview averages, quiz
      ordering (worst-first), at-risk flag on both trigger conditions,
      activity zero-fill for a day with no events.
- [ ] Zero-student and zero-quiz course cases.

## Frontend tasks

- [ ] `npm install recharts` (pending answer to open question #1).
- [ ] `frontend/src/services/analytics.ts` + response types in
      `types/index.ts` for the four endpoints.
- [ ] `frontend/src/pages/instructor/AnalyticsPage.tsx`:
  - [ ] Overview stat cards (reuse existing dashboard `StatCard`-style
        component).
  - [ ] Quiz performance table (reuse gradebook table primitives), worst
        avg-score first, visually flagging quizzes below the quiz's own
        `passing_score`.
  - [ ] Student progress table (reuse roster table conventions), sortable
        by progress %, at-risk rows visually flagged.
  - [ ] Activity trend chart (recharts line or bar), last 30 days.
  - [ ] Empty states (no quizzes yet / no students yet) using the Phase 20
        icon+CTA `EmptyState` pattern.
- [ ] Route: `/instructor/courses/:code/analytics` in `App.tsx`.
- [ ] Link from `ManageCoursePage`'s quick-actions row (near the existing
      Gradebook/Students/Quizzes links, `ManageCoursePage.tsx:529-547`).

## Success criteria

- [ ] Instructor sees class overview at a glance (students, avg progress,
      avg grade, active-this-week).
- [ ] Instructor can identify struggling quizzes (low avg score / low pass
      rate) without opening the gradebook.
- [ ] Instructor can identify at-risk students (low progress or inactivity)
      in one sortable list.
- [ ] Activity chart shows lesson/quiz activity trend over the last 30
      days.
- [ ] Page loads in a single request burst, <2s locally.

## Verification

- [ ] `cd backend && pytest` — full suite, new analytics tests included.
- [ ] `cd frontend && npx tsc --noEmit` — 0 errors.
- [ ] `cd frontend && npm run lint` — 0 new errors.
- [ ] `/verify-stack` output shown.
- [ ] Manual click-through: course with real seeded data (overview numbers
      sane, worst quiz surfaced, at-risk students flagged correctly,
      30-day chart renders); course with zero quizzes; course with zero
      students.
