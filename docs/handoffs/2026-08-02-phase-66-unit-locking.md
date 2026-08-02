# Handoff: Phase 66 instructor unit locking — PR open, not merged

## Current state
Phase 66 is code-complete on `feat/phase-66-unit-locking`. **PR #95 open, NOT merged**
(https://github.com/Cesar6060/LMS/pull/95). All 23 spec checklist items done.
- Verified: pytest **945** (main had 892), tsc 0, lint 0 (+1 known), vitest **132**,
  `makemigrations --check` clean. Manual click-through done on local Docker (VGD101).
- Migration `courses/0025_unit_is_locked` — `db_default=False`, reverse tested down/up,
  and a raw INSERT omitting the column was proven to succeed with `False`.
- Backend: `courses/{models,permissions,serializers,views}.py`, `quizzes/views.py`,
  `gamification/services.py`, `notifications/signals.py`,
  `courses/management/commands/_content_upsert.py` (docstring only).
- Frontend: `types/index.ts`, `services/courses.ts`, `OutlineUnitCard.tsx` (+ new test),
  `ManageCoursePage.tsx`, `CourseDetailPage.tsx`, `CourseSidebar.tsx`,
  `CoursePlayerPage.tsx`, `CourseMapPath.tsx`, `lib/courseProgress.ts` (+ tests).

## In progress / not done
- **`code-reviewer` never ran** — the agent died on an API session limit. I did the review
  manually (queryset sweep + contract-drift check, which caught nullable `passing_score`),
  but an independent review pass before merge is worth it.
- Three findings deliberately deferred, all recorded in the spec and PR body: the
  `_badge_satisfied` `CRITERIA_LESSONS_DONE` lock-filter asymmetry, `course_map` still
  emitting locked node `id`s, and the player's neutral empty state on a pasted locked URL.
- Carried, untouched: branch protection on `main`; whether to track `.claude/`;
  `THROTTLE_SLIDE_IMPORT` ceiling; phase-61 slide-import smoke test; JAVA101
  answer-rotation reseed; phase-56 + 64 click-throughs; Sentry LoginPage; Dependabot
  #68/#86/#87/#88 (React 19, eslint 10, vite 8, tailwind 4 each need a companion bump).

## Next steps
1. Optionally re-run `code-reviewer` on `git diff main...HEAD` before merging PR #95.
2. Merge PR #95 when ready — **this deploys**. Then verify with BOTH
   `/api/health/?deep=1` AND a real content read (demo-login → `GET
   /api/courses/courses/DEMO101/units/`, expect `is_locked: false` + `lesson_count`).
3. Decide the deferred badge-asymmetry question (should a completion inside a
   later-locked unit still count toward `lessons_done` badges?).
4. Add branch protection on `main` (require both CI jobs).

## Decisions made
- **Locked units excluded from denominators unconditionally**, not per-viewer — these
  measure what a student can reach, so an instructor viewing a gradebook sees the same
  math the student does.
- **A locked unit is transparent to the course map's sequence chain**, not a wall.
  Otherwise locking unit 2 sequence-locks units 3+ for the whole class.
- **Locked beats completed** on the map — a lesson finished before the lock still reads
  locked, and its completion leaves both numerator and denominator.
- **Quizzes in locked units leave the gradebook's `possible` total**, rather than scoring
  zero — otherwise locking silently tanks every student's grade.
- **Demo guard keyed on `is_locked` being in the payload**, not on unit writes generally,
  so a demo instructor can still rename a unit.
- **Reseeds never touch `is_locked`** — it is instructor state, not blueprint state.
- **Notification suppressed for lessons authored into a locked unit** — authoring there is
  supported, announcing it verbatim is not.

## Gotchas discovered
- **The per-object gate is never the leak.** Both adversarial passes found the same shape:
  `require_unit_unlocked` held everywhere, while flat list actions, aggregates and a
  `post_save` signal leaked, because a DRF `list` never calls `get_object()`. When adding
  a gate, sweep list/aggregate/signal surfaces separately.
- **A `QuizAttempt` is a full copy of its quiz** — `AttemptAnswer` renders `question_text`
  and `correct_choice_text`. Any "past attempts" endpoint needs the same gate as the quiz.
- A concurrent subagent's `npm install` left `node_modules` without
  `@rollup/rollup-darwin-arm64`, breaking vitest until reinstalled. Avoid parallel agents
  running npm in the same tree.
- `QuizAttempt.points_earned` is a read-only property, not a field — don't pass it to
  `objects.create()`.
- `@testing-library/user-event` is NOT a dependency here; use `fireEvent`.
- Browser clicks fired ~3s after navigation can land before hydration and silently no-op.
- Carried, still true: never run pytest concurrently with review subagents.

## Files to read first
1. `docs/specs/phase-66-unit-locking.md` — checklist plus both adversarial-pass writeups.
2. `backend/courses/permissions.py` — `require_unit_unlocked`, `locked_unit_ids_for`.
3. `backend/courses/views.py` — the gate call sites, `course_map`, and every denominator.
4. `backend/courses/serializers.py` — `UnitSerializer.to_representation` (the lock shape).
5. PR #95 body — the full HELD/BROKEN table and the post-deploy verification commands.
