# Phase 31: Instructor Analytics Dashboard

Supersedes `phase-21-instructor-analytics-dashboard.md` (deferred 2026-07-18).
That spec was re-validated on 2026-07-19 against everything shipped since:
Phase 18 (assignments removed), Phases 22–29 (UI restructure — quick-actions
row replaced by `CourseToolsNav`; lesson comprehension checks added), and
Phase 30 (gamification). All open questions from the old spec are now decided
(see Decisions). **Branch note:** depends on Phase 30's `gamification` app —
branch from `feat/phase-30-gamification` (or from main once it merges).

## Goal

Give the instructor a per-course view of how the class is actually doing:
overview stats, which assessments students are struggling with (both graded
unit quizzes and lesson comprehension checks), which students are falling
behind (including a dead-streak disengagement signal), and a 30-day activity
trend — so problems can be caught while there's still time to act, not just
at grading time.

## Decisions (interview 2026-07-19)

1. **Chart library:** add `recharts` (already penciled into PLAN.md's
   dependency table), scoped to the one activity-trend chart — not a
   platform-wide charting adoption.
2. **Quiz scope:** cover BOTH quiz systems as two separate sections —
   "Unit quizzes" (graded, `quizzes` app) and "Lesson checks"
   (`LessonQuizAttempt`, perfect-score-to-pass, not graded). Kept separate
   because score semantics differ; do not merge into one table.
3. **Gamification:** show each student's **current streak** in the students
   table (global `GameProfile.current_streak` — cheap read, strong
   disengagement signal). No per-course XP aggregation, no level/badges here.
4. **Activity trend sources:** all three — lessons completed
   (`LessonProgress.completed_at`), unit-quiz attempts
   (`QuizAttempt.completed_at`), lesson-check attempts
   (`LessonQuizAttempt.completed_at`) — per day, last 30 days, zero-filled.

Carried over from Phase 21 scoping (still valid, re-verified):

- Per-course only (like gradebook/roster), no cross-course rollup.
- "At-risk" = progress < 50% OR inactive 7+ days — the exact
  `StudentRosterSerializer.get_is_inactive` logic (`serializers.py:497`,
  including the null-`last_activity_at` fallback to `enrolled_at`). No new
  scoring model.
- Instructor-only endpoints in the `courses` app following the
  gradebook/roster pattern (`require_course_instructor`,
  `courses/permissions.py:26`). Note: routes registered like the gradebook
  resolve under the existing double prefix — real URLs are
  `/api/courses/courses/{code}/analytics/...` (see `tests.py:526` for the
  gradebook precedent).
- Read-only page; gradebook owns grade editing.

## Out of scope

- Cross-course aggregate view across all of an instructor's courses.
- Historical range beyond 30 days; CSV export of analytics; question-level
  item analysis within a quiz.
- Predictive/ML risk scoring — threshold rules only.
- Per-course XP aggregation, levels, badges in instructor views (Phase 32
  territory).
- Editing anything from this page.
- New models or migrations — this phase is pure aggregation over existing
  tables (`QuizAttempt`, `LessonQuizAttempt`, `LessonProgress`, `Enrollment`,
  `GameProfile`).

## API endpoints

All: instructor of the course only (`require_course_instructor`), colocated
with gradebook/roster routes in `courses/urls.py`.

```
GET courses/<str:course_code>/analytics/overview/   # class-level key metrics
GET courses/<str:course_code>/analytics/quizzes/    # unit_quizzes[] + lesson_checks[]
GET courses/<str:course_code>/analytics/students/   # per-student row incl. streak + at_risk
GET courses/<str:course_code>/analytics/activity/   # 3 counts per day, last 30 days
```

## Backend tasks

### `backend/courses/views.py`

- [x] `analytics_overview(request, course_code)`: returns `student_count`
      (active enrollments), `avg_progress_percentage` (mean of per-student
      lesson-completion %, same calc as
      `StudentRosterSerializer.get_progress_percentage`),
      `avg_grade_percentage` (mean of per-student weighted grade, reusing
      `calculate_weighted_grade` at `views.py:888` with the course's
      `grading_config`; students with no grade components excluded from the
      mean), `active_last_7_days` (enrollments with `last_activity_at`
      within 7 days, same fallback semantics as `get_is_inactive`).
- [x] `analytics_quizzes(request, course_code)`: returns
      `{unit_quizzes: [...], lesson_checks: [...]}`.
      - `unit_quizzes`: per `quizzes.Quiz` in the course — `title`,
        `unit_title`, `passing_score`, `avg_score` (mean of best attempt per
        student, consistent with the gradebook's best-attempt convention at
        `views.py:937-968`), `pass_rate` (students with ≥1 passed attempt /
        students with ≥1 attempt), `completion_rate` (students with ≥1
        attempt / active enrollments). Ordered ascending by `avg_score` so
        struggling quizzes surface first.
      - `lesson_checks`: per lesson that has `LessonQuestion`s — `title`,
        `unit_title`, `attempted_count`, `passed_count`,
        `stuck_count` (students who attempted but never passed),
        `avg_attempts_to_pass` (mean `attempt_number` of each student's
        first passing `LessonQuizAttempt`; null if nobody passed). Ordered
        by `stuck_count` desc, so blockers surface first.
- [x] `analytics_students(request, course_code)`: per active enrollment —
      `student` (id/name/email as in roster), `progress_percentage`,
      `quiz_average`, `weighted_grade` (same calcs as gradebook),
      `last_activity_at`, `current_streak` (from `GameProfile`; 0 when no
      profile exists — do NOT create profiles here), `at_risk`
      (progress < 50 OR the `get_is_inactive` rule). Bulk-fetch: one query
      per data source (`LessonProgress` grouped counts like
      `views.py:974-979`, one `GameProfile` `in_bulk`/values query) — no
      per-student N+1.
- [x] `analytics_activity(request, course_code)`: last 30 days (inclusive of
      today, current timezone via `TruncDate`), one entry per date:
      `{date, lessons_completed, quiz_attempts, lesson_check_attempts}`.
      Sources: `LessonProgress(completed=True).completed_at`,
      `QuizAttempt.completed_at`, `LessonQuizAttempt.completed_at`, all
      filtered to this course's lessons/quizzes and enrolled-student events.
      Zero-fill missing days server-side so the frontend never has to.
- [x] Edge cases: zero enrolled students, zero quizzes, zero lesson checks —
      zeroed/empty structures with 200, never errors. `avg_*` are null (not
      0) when there is no data to average.

### `backend/courses/urls.py`

- [x] Add the four paths, colocated with gradebook/roster routes
      (`urls.py:30-41`).

### Serializers

- [x] Plain dict responses assembled in the views (gradebook precedent) OR
      lightweight serializers — match whichever the gradebook endpoint does
      today; don't invent a new pattern.

### Tests (`backend/courses/tests.py`)

- [x] Permission boundary for EACH of the four endpoints: course instructor
      (200), instructor of a different course (403), enrolled student (403),
      anonymous (401/403) — model on `TestGradebook` (`tests.py:521`).
- [x] Overview correctness against seeded fixtures (known averages;
      `active_last_7_days` counts fresh vs stale `last_activity_at`).
- [x] Unit-quiz metrics: best-attempt avg matches gradebook convention;
      worst-avg-first ordering; pass_rate/completion_rate denominators.
- [x] Lesson-check metrics: stuck student counted (attempted, never passed);
      `avg_attempts_to_pass` uses first passing attempt; lesson with no
      questions excluded.
- [x] Students: at-risk flag fires on each trigger independently (low
      progress with recent activity; high progress but 8+ days inactive);
      `current_streak` present, and 0 for a student with no `GameProfile`.
- [x] Activity: zero-fill for a day with no events; all three series
      counted; event outside 30-day window excluded; other-course events
      excluded.
- [x] Zero-student and zero-quiz course cases (200 with empty/zeroed body).

## Frontend tasks

- [x] `npm install recharts` (new dependency, approved in interview).
- [x] `frontend/src/services/analytics.ts`: `analyticsService` object using
      the shared `api` axios instance (per `.claude/rules/frontend.md` /
      `courses.ts` convention), four methods; response types co-located in
      the service file and exported (the `courses.ts:7-142` pattern).
- [x] `frontend/src/components/instructor/CourseToolsNav.tsx`: add an
      `Analytics` tab to the tabs array (`CourseToolsNav.tsx:17-23`) →
      `/instructor/courses/${courseCode}/analytics`. This surfaces the link
      on ManageCourse/Gradebook/Roster automatically.
- [x] Route in `App.tsx` (`:272-320` block): `<InstructorRoute>` wrapping
      `AnalyticsPage`, mirroring the gradebook route.
- [x] `frontend/src/pages/instructor/AnalyticsPage.tsx`, wrapped in
      `PageContainer` (default `max-w-7xl` — keep instructor pages wide) +
      `CourseToolsNav`, with `isForbidden(err)` → `<AccessDenied/>` and
      `Skeleton`/`SkeletonStatCard` loading states, matching
      GradebookPage/StudentRosterPage:
  - [x] Overview stat cards: `Card`/`CardContent py-6` grid, `text-3xl
        font-bold` number + `text-sm text-muted-foreground` label — the
        exact `GradebookPage.tsx:185-207` convention (there is no shared
        StatCard component; do not invent one this phase).
  - [x] Unit-quiz performance table: gradebook table conventions
        (`Card > CardContent p-0 > overflow-x-auto`, zebra rows), worst
        avg-score first, visually flag quizzes whose `avg_score` is below
        their own `passing_score`.
  - [x] Lesson-checks table: same table conventions — attempted / passed /
        stuck / avg attempts columns, stuck-heavy lessons flagged.
  - [x] Students table: client-side sortable following the
        `StudentRosterPage.tsx:76-160` pattern (`SortField` state, header
        buttons, `aria-sort`), default sort: at-risk first. Columns:
        student, progress (compact inline bar per
        `StudentRosterPage.tsx:387-395`), quiz avg, weighted grade, streak
        (reuse `StreakFlame` `size='sm'` or flame+number), last activity,
        at-risk flag (visually prominent row treatment — remember the
        readability preference: important info prominent).
  - [x] Activity trend chart (recharts, last 30 days, three series). Load
        the `dataviz` skill BEFORE writing any chart code.
  - [x] Empty states: inline `Card > CardContent py-12 text-center` blocks
        (lucide icon + heading + text), per `GradebookPage.tsx:210-235` —
        there is no shared `EmptyState` component. Cases: no students yet,
        no unit quizzes, no lesson checks, no activity yet.

## Success criteria

- [x] Instructor sees class overview at a glance (students, avg progress,
      avg grade, active-this-week).
- [x] Instructor can spot struggling unit quizzes AND blocking lesson
      checks without opening the gradebook.
- [x] Instructor can identify at-risk students in one sortable list, with
      streak as a disengagement signal.
- [x] Activity chart shows the three-series 30-day trend.
- [x] Page loads in a single request burst, <2s locally.

## Verification

- [x] `cd backend && pytest` — full suite, new analytics tests included
      (remember `docker compose restart backend` before manual checks).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 new errors (warning baseline ~25).
- [x] `/verify-stack` output shown.
- [ ] Manual click-through:
  - [ ] Course with real seeded data: overview numbers sane; worst quiz
        surfaced first; a stuck lesson check surfaces; at-risk rows flagged
        for both trigger conditions; streak column shows real values;
        30-day chart renders with all three series.
  - [ ] Analytics tab visible in `CourseToolsNav` on ManageCourse,
        Gradebook, and Roster pages; active-state pill correct on the
        analytics page.
  - [ ] Course with zero quizzes; course with zero students (empty states,
        no errors).
  - [ ] Enrolled student navigating to `/instructor/courses/:code/analytics`
        gets `AccessDenied`; direct API call as student gets 403.
