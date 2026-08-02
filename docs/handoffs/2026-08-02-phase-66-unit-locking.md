# Handoff: Phase 66 instructor unit locking — PR open, not merged

## Current state
Phase 66 code-complete on `feat/phase-66-unit-locking`. **PR #95 open, NOT merged**
(https://github.com/Cesar6060/LMS/pull/95). All 23 spec checklist items done.
- Verified: pytest **945** (main: 892), tsc 0, lint 0 (+1 known), vitest **132**,
  `makemigrations --check` clean. Manual click-through done on local Docker (VGD101).
- Migration `courses/0025_unit_is_locked` — `db_default=False`, reverse tested down/up,
  and a raw INSERT omitting the column proven to succeed with `False`.
- Backend: `courses/{models,permissions,serializers,views}.py`, `quizzes/views.py`,
  `gamification/services.py`, `notifications/signals.py`. Frontend: `types/index.ts`,
  `services/courses.ts`, `OutlineUnitCard.tsx` (+test), `ManageCoursePage.tsx`,
  `CourseDetailPage.tsx`, `CourseSidebar.tsx`, `CoursePlayerPage.tsx`,
  `CourseMapPath.tsx`, `lib/courseProgress.ts` (+tests).

## In progress / not done
- **`code-reviewer` never ran** — agent died on an API session limit. I reviewed manually
  (queryset sweep + contract drift, which caught nullable `passing_score`); an independent
  pass before merge is worth it.
- Three findings deliberately deferred, recorded in the spec and PR body: `_badge_satisfied`
  `CRITERIA_LESSONS_DONE` lock-filter asymmetry; `course_map` still emitting locked node
  `id`s; the player's neutral empty state on a pasted locked-lesson URL.
- Carried, untouched: branch protection on `main`; whether to track `.claude/`;
  `THROTTLE_SLIDE_IMPORT` ceiling; phase-61 slide-import smoke test; JAVA101 answer-rotation
  reseed; phase-56 + 64 click-throughs; Sentry LoginPage; Dependabot #68/#86/#87/#88.

## Next steps
1. Optionally re-run `code-reviewer` on `git diff main...HEAD` before merging PR #95.
2. Merge PR #95 when ready — **this deploys**. Verify with BOTH `/api/health/?deep=1` AND a
   real content read (demo-login → `GET /api/courses/courses/DEMO101/units/`, expect
   `is_locked: false` + `lesson_count`).
3. Decide the deferred badge question: should a completion inside a later-locked unit still
   count toward `lessons_done` badges?
4. Add branch protection on `main` (require both CI jobs).

## Decisions made
- **Denominators exclude locked units unconditionally**, not per-viewer — they measure what
  a student can reach, so the gradebook shows the same math the student sees.
- **A locked unit is transparent to the course map's sequence chain**, not a wall —
  otherwise locking unit 2 sequence-locks units 3+ for the whole class.
- **Locked beats completed** on the map; a pre-lock completion leaves both sides of the math.
- **Locked units' quizzes leave the gradebook `possible` total** rather than scoring zero,
  which would silently tank every student's grade.
- **Demo guard keyed on `is_locked` being in the payload**, not unit writes generally, so a
  demo instructor can still rename a unit.
- **Reseeds never touch `is_locked`** — instructor state, not blueprint state.
- **New-lesson notification suppressed inside a locked unit** — authoring there is
  supported, announcing the title verbatim is not.

## Gotchas discovered
- **The per-object gate is never the leak.** Both adversarial passes found the same shape:
  `require_unit_unlocked` held everywhere, while flat lists, aggregates and a `post_save`
  signal leaked — a DRF `list` never calls `get_object()`. Sweep those surfaces separately.
- **A `QuizAttempt` is a full copy of its quiz** (`AttemptAnswer` renders `question_text`
  and `correct_choice_text`), so any past-attempts endpoint needs the same gate.
- A concurrent subagent's `npm install` left `node_modules` without
  `@rollup/rollup-darwin-arm64`, breaking vitest. Avoid parallel agents running npm.
- `QuizAttempt.points_earned` is a read-only property — don't pass it to `objects.create()`.
- `@testing-library/user-event` is NOT a dependency here; use `fireEvent`.
- Browser clicks ~3s after navigation can land before hydration and silently no-op.
- Carried: never run pytest concurrently with review subagents.

## Files to read first
1. `docs/specs/phase-66-unit-locking.md` — checklist plus both adversarial writeups.
2. `backend/courses/permissions.py` — `require_unit_unlocked`, `locked_unit_ids_for`.
3. `backend/courses/views.py` — gate call sites, `course_map`, every denominator.
4. `backend/courses/serializers.py` — `UnitSerializer.to_representation` (the lock shape).
5. PR #95 body — full HELD/BROKEN table and post-deploy verification commands.
