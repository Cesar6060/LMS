# Phase 66 — Instructor Unit Locking

## Goal

Let an instructor lock individual units in a course so content that already exists stays
hidden from students until the class reaches it. A locked unit is **visible but locked**:
students see the unit title, lesson count, and a lock indicator in every course surface
(course detail, player sidebar, course map), but its lessons, sections, questions, and
unit quizzes are inaccessible — enforced server-side at every read endpoint, not just
hidden in the UI. The instructor toggles the lock manually from the course outline editor
(and always sees full content themselves). Locked units are excluded from all progress
denominators (progress %, gradebook, analytics, course-complete badge), so a student who
finishes everything currently unlocked reads 100%. New and existing units default to
unlocked; nothing changes for a course whose instructor never touches the feature.

## Out of scope

- Release dates / scheduled auto-unlock (manual toggle only).
- Sequential per-student unlocking (the course map's soft sequence gating stays as-is).
- Lesson-level or quiz-level locks — the unit is the only lockable granularity.
- Revoking XP, badges, or `LessonProgress` already earned when a unit is locked
  after the fact (grant-only ledger stays untouched; locked-unit completions simply
  drop out of both numerator and denominator).
- Discussions (they attach to Course, not Unit — unaffected).
- Any change to the demo-course clone beyond confirming default-unlocked behavior.

## Design decisions (locked in with user)

- Unlock mode: **manual toggle** by the instructor.
- Student view: **visible but locked** — title + lesson count + "Locked by your
  instructor"; no lesson titles, no content.
- Progress math: **exclude locked units** from every denominator (and their completed
  lessons from numerators, for consistency).
- Default: **unlocked** (`default=False`), so existing rows, seeds, and the demo clone
  are unaffected.

## Backend tasks

- [x] **Model + migration** — add `is_locked = models.BooleanField(default=False, db_default=False)`
      to `Unit` (`courses/models.py:67`). Migration `courses/0025_*` must be additive and
      old-code-safe (`db_default` is required — see CLAUDE.md gotcha; old code keeps
      serving during the pre-deploy migrate window). Run the db-migration-checker agent
      on it.
- [x] **Enforcement helper** — `require_unit_unlocked(user, unit)` in
      `courses/permissions.py`: no-op for the course instructor
      (`is_course_instructor`), otherwise `PermissionDenied({'detail': 'This unit is
      locked by your instructor.'})` when `unit.is_locked`. All denials are 403 with
      `{'detail': ...}` per `.claude/rules/backend.md`.
- [x] **Gate lesson-level reads** (`courses/views.py`) — call the helper (via
      `lesson.unit`) in: `LessonViewSet.retrieve` (:271), `UnitLessonsView` (:389),
      `lesson_sections` (:2645), `LessonProgressView.get_object` (:495 — blocks writes
      too), and the lesson-question endpoints (`lesson_questions*`, questions-status,
      quiz-session start/answer — views.py:2076/2238/2343/2383/2402).
- [x] **Gate quiz reads/writes** (`quizzes/views.py`) — unit quiz list (:43), quiz
      detail (:85), submit (:192), session start/answer (:324/:368/:386) via
      `quiz.unit`; filter locked units out of the flat course-wide list
      `GET /api/courses/{code}/quizzes/` (:524) for non-instructors.
- [x] **Serializer shaping** — expose `is_locked` on `UnitSerializer`
      (`courses/serializers.py:398`); for non-instructor viewers a locked unit
      serializes with `lessons: []` plus a `lesson_count` field so the UI can show
      "N lessons · Locked" (follow the role-branched `to_representation` precedent at
      serializers.py:476-485). Applies to `CourseSerializer.units`,
      `InstructorCourseSerializer` (instructor always gets full lessons), and the
      standalone `CourseUnitsView` / `UnitViewSet` list.
- [x] **Toggle write path** — make `is_locked` writable on `UnitCreateSerializer`
      (serializers.py:406), which `UnitViewSet` already uses for `update/partial_update`
      (views.py:191-194) behind `IsEnrolledOrInstructor` (writes = course instructor).
      Add `require_not_demo` to the lock-toggle write branch (shared-surface write per
      demo policy, `core/demo.py:49`).
- [x] **Progress denominators** — exclude lessons of locked units (for the student in
      question) from numerator and denominator at every site the explorer mapped:
      `CourseProgressView` (views.py:542), gradebook (:1051), gradebook export (:1178),
      `_analytics_student_rows` (:1291), `student_grade_summary` (:2026),
      `StudentRosterSerializer` (serializers.py:754), and the course-complete badge
      `_badge_satisfied` (`gamification/services.py:237-251`).
- [x] **Course map** — `course_map` (views.py:3144): every node in a locked unit gets
      `state='locked'` regardless of completion, with a `lock_reason: 'instructor'`
      field (existing sequence-locking sends `lock_reason: 'sequence'`) so the frontend
      can show the right tooltip.
- [x] **Dashboard continue-learning** — the next-lesson picker (views.py:682-683)
      skips lessons in locked units.
- [x] **Seed safety (verify, no code expected)** — `upsert_unit`
      (`_content_upsert.py:189`) writes only `title`, so lock state survives reseeds;
      `clone_course_for_demo.py:107` passes order/title only, so cloned units default
      unlocked. Add a regression assertion to `test_content_upsert.py` that reseeding
      preserves `is_locked=True`.
- [x] **Tests** (`courses/`, `quizzes/`, `gamification/`) — permission-boundary pytest
      for every gated endpoint (instructor / enrolled student / anonymous, per
      backend rules); locked unit serializes with empty `lessons` + `lesson_count` for
      students and full lessons for the instructor; toggle PATCH: instructor 200,
      student 403, demo 403 `demo_blocked`; denominator exclusion for progress %,
      gradebook, and course-complete badge (badge earnable with a locked unit
      outstanding); course map emits `locked` + `lock_reason='instructor'`;
      continue-learning skips locked units; reseed preserves lock.

## Frontend tasks

- [x] [P] **Types** — add `is_locked: boolean` (and `lesson_count?: number`) to `Unit`
      (`types/index.ts:52`) and `UnitWithLessons` (`services/courses.ts:37`); extend
      `CourseMapNode` with `lock_reason?`. No new service functions — `updateUnit`
      (`services/courses.ts:211`) already PATCHes `Partial<Unit>`.
- [x] **Instructor toggle** — `OutlineUnitCard` (`components/manage/OutlineUnitCard.tsx`):
      Lock/Unlock icon `Button` in the unit header row (:288-339), following the
      `ThreadDetailPage` lock-toggle pattern (:275-282, aria-label swap) and the
      optimistic PATCH-with-revert handler shape from `LessonEditorPage.tsx:142-157`.
      Locked units show a visible "Locked" badge on the card so state is prominent.
      Real buttons, wide page — both already the norm here.
- [x] [P] **Student course detail** — `CourseDetailPage.tsx` unit cards (:450-498):
      locked unit renders title, "N lessons", `<Lock>` icon and "Locked by your
      instructor"; no lesson rows (backend sends none). Instructor sees full content
      plus a lock chip. Reuse the existing locked-lesson visual branch (:481-490).
- [x] [P] **Player sidebar** — `CourseSidebar.tsx`: locked unit header is
      non-expandable, muted, with `<Lock>` icon (styling per `CourseMapPath.tsx:67-78`
      muted/locked classes); `findFirstIncompleteLesson` auto-resume in
      `CoursePlayerPage.tsx:138-170` and `lib/courseProgress.ts` helpers
      (`getNextLesson`, `getUnitProgress`) skip locked units — update
      `courseProgress.test.ts` accordingly.
- [x] [P] **Course map** — `CourseMapPath.tsx`: when `lock_reason === 'instructor'`,
      tooltip/title reads "Locked by your instructor" instead of "Complete the
      previous lesson to unlock" (:129-136).
- [x] **Type check + lint + vitest** — `npx tsc --noEmit` clean, `npm run lint` clean
      (+1 known), vitest suite green including updated `courseProgress` tests.

## Verification

- [x] `cd backend && pytest` — all green, including the new cases:
  - `test_locked_unit_hidden_from_student_course_detail` (empty `lessons`, has
    `lesson_count`, `is_locked: true`)
  - `test_locked_unit_full_for_instructor`
  - `test_lesson_read_in_locked_unit_403_for_student` (lesson detail, sections,
    questions, progress GET/PATCH)
  - `test_quiz_endpoints_in_locked_unit_403_for_student` (detail, submit, session)
  - `test_course_quiz_list_filters_locked_units`
  - `test_lock_toggle_permissions` (instructor 200 / student 403 / anon 401 /
    demo 403 `demo_blocked`)
  - `test_progress_percent_excludes_locked_units`
  - `test_course_complete_badge_ignores_locked_units`
  - `test_course_map_instructor_lock_state`
  - `test_reseed_preserves_unit_lock`
- [x] `makemigrations --check` clean after the new migration; db-migration-checker
      agent reports the migration additive and old-code-safe (`db_default` present).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors; `npm run lint` — 0 (+1 known);
      `npx vitest run` — green.
- [x] `/verify-stack` PASS with output shown.
- [x] Manual flow (local Docker): as instructor, open Manage Course → lock Unit 2 →
      badge appears. As an enrolled student: course detail shows Unit 2 title +
      lock, no lessons; player sidebar shows it locked and auto-resume lands on an
      unlocked lesson; pasting a Unit-2 lesson URL directly shows the 403/blocked
      state; course map shows the unit's nodes locked with the instructor tooltip;
      progress % matches unlocked-only math. Unlock Unit 2 → everything restores
      without a reload artifact.
- [x] Run the adversarial-tester agent against the new endpoints (direct-id access,
      IDOR across courses, demo account, unenrolled student).

## Adversarial pass — findings and fixes

The per-object gate (`require_unit_unlocked`) and the lock-toggle write path held
against every direct probe: cross-course IDOR, a non-course instructor, student
and anonymous toggles, demo bypass via PUT/PATCH/`reorder`, malformed `is_locked`
payloads, and divide-by-zero when every unit is locked. What leaked were the
surfaces that never call the gate — flat lists and aggregate math. All fixed,
each with a permanent regression test:

1. **`GET /api/courses/lessons/` leaked locked lesson titles and bodies** (high).
   The gate lives in `get_object()`, which a DRF list action never calls.
   Fixed by excluding locked units from the `list` queryset for non-instructors.
2. **`GET /api/quizzes/{id}/attempts/` leaked the whole quiz** (high) — an attempt
   renders `question_text` and `correct_choice_text`, so taking a quiz once bought
   permanent access to it after the unit was locked. Now gated.
3. **`course_map` printed real lesson/quiz titles** for instructor-locked nodes
   (medium-high), the one surface contradicting the "no lesson titles" rule.
   Locked nodes now serialize as `Locked lesson` / `Locked quiz`.
4. **`_analytics_student_rows` kept counting locked-unit quiz attempts** (medium),
   so analytics disagreed with the gradebook and drove bogus `at_risk` flags.
5. **`CourseUnitsView.perform_create` accepted `is_locked=True` without the demo
   guard** (defensive; not reachable today since the demo account is not an
   instructor). Now mirrors `UnitViewSet.perform_update`.
