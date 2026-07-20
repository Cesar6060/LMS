# Handoff: Phase 32 — Duolingo-style quiz UX & deeper gamification

## Current state
Phase 32 **implemented + verified + committed + pushed**. The whole unpushed
chain (Phases 29–32) now lives on branch `feat/phase-32-duolingo-quiz-ux`
(created at the old `feat/phase-31-instructor-analytics` HEAD, which it
supersedes), pushed to remote `lms` — **PR #17 open against `Cesar6060/LMS`
main: https://github.com/Cesar6060/LMS/pull/17**.
Commits: `f930158` feat (Phase 32 code), `c45087a` docs (spec + this handoff).

Backend:
- `quizzes`: `QuizAttempt.status` (`in_progress`/`completed`, default completed) +
  nullable `completed_at` (auto_now_add removed — every completed-attempt create
  path now sets it explicitly, including `seed_data`); `AttemptAnswer.mastered_at`.
  Session endpoints `POST /quizzes/<id>/session/start/`, `GET .../session/`,
  `POST .../session/answer/` with auto-finalize (first-try score, `award_quiz_pass`
  on pass, result embeds the `submit_quiz`-shaped attempt + gamification delta).
  `max_attempts` enforced against completed attempts only.
- `courses`: `LessonAttemptAnswer` model; `LessonQuizAttempt.status`; mirrored
  `POST/GET /lessons/<id>/quiz-session/...` endpoints. **Attempt cap retired**
  (`max_quiz_attempts` ignored, field kept for rollback); mastery ⇒ `passed=True`,
  `score` = first-try correct count. Legacy `LessonQuestionAnswer` synced on every
  graded answer so `questions-status` / completion gating hold.
- Every attempt consumer filtered to `status='completed'` (serializers, attempts
  history, quick-grade, gradebook + export, Phase 31 analytics, enhanced dashboard,
  grade summary, questions-status).
- `gamification`: `GameProfile.streak_freezes` (cap 2, +1 per level gained,
  auto-consumed when `0 < missed_days <= freezes`, else reset without consuming);
  `freezes_earned`/`freezes_used`/`streak_freezes` in delta + profile payload.
- Migrations: `quizzes/0003`, `courses/0015`, `gamification/0003` (applied in dev).

Frontend:
- `components/quiz/QuizSessionFlow.tsx` — shared generic mastery flow (progress
  bar, big choice buttons, check → feedback banner with mascot → continue,
  re-queue, resume via GET-then-start, keyboard 1–9/Enter).
- `components/gamification/Mascot.tsx` ("Circuit", poses idle/cheer/encourage/
  celebrate, theme-aware, CSS-only animation), `StreakFreezeChip.tsx`;
  freeze toasts in `useGamificationFeedback`.
- `QuizDetailPage` (resume banner, mastered-vs-passed result screen, retake only
  when failed + attempts remain), `LessonQuizSection` (session flow, "Mastered!"
  completion, practice again, no attempt caps), dashboard greeting + freeze chips
  (Dashboard + Settings→Achievements), instructor max-attempts inputs removed
  (`LessonEditorPage`, `LessonQuestionsManager`), `LessonQuestions.tsx` deleted.

Verified: **pytest 326 passed** (276 baseline + 50 new); **tsc 0 errors**;
**lint 0 errors / 22 warnings** (baseline 25); code-reviewer agent ran — its 3
findings (seeded attempts missing `completed_at`, answer-race 500, legacy lesson
submit counting in-progress rows) all fixed and re-verified.

## In progress / not done
- **Manual click-through** — the only unchecked spec section (§Verification).
  Backend restarted, endpoints live (401 unauth spot-checked). Ready to click.
- Duplicate in-progress sessions from *racing start requests* remain possible
  (no partial unique index); answer races are now safe via `get_or_create`.
  Reviewer rated LOW; acceptable for classroom use.
- Phase 31's manual click-through is also still open (see its handoff).

## Next steps
1. Manual click-through per spec §Verification (unit-quiz mastery + resume +
   abandoned-attempt check, lesson-check loop, streak-freeze via backdated
   `last_activity_date` in dbshell, mascot in both themes, instructor checks).
2. Check off the manual section in `docs/specs/phase-32-duolingo-quiz-ux.md`.
3. Review + merge PR #17 (https://github.com/Cesar6060/LMS/pull/17 — carries
   Phases 29–32). After merge, delete the superseded local phase branches.

## Decisions made
- Session resume = `POST start` returns the existing in-progress attempt (200)
  vs 201 for a fresh one; frontend flow does GET-then-start on mount.
- Re-queue order: unanswered questions first (original order), then missed ones.
- Unit-quiz finalize response embeds the full `QuizAttemptSerializer` payload as
  `result` so the result screen is shared with the legacy shape.
- Lesson `attempt_number` derived from `Max(attempt_number)+1` (not count) in
  both session start and legacy submit so in-progress rows can't collide with
  the `unique_together`.
- Freeze earn ordering: consume (streak update) happens before earn (level-up)
  inside `_award` — a freeze earned by this action can't be spent by it.
- Answer writes use `get_or_create` keyed on `(attempt, question)` — race-safe,
  first-try record immutable by construction.

## Gotchas discovered
- **Django 4.2 `update_or_create` passes `update_fields` on the update path**,
  which silently drops `LessonQuestionAnswer.is_correct` recomputed in its
  custom `save()`. The session flow uses `get_or_create` + full save. The
  legacy `answer_lesson_question` view still uses `update_or_create` — its
  changed-answer path has this latent staleness bug (pre-existing, untouched).
- `QuizAttempt.completed_at` no longer auto-populates: any new
  `QuizAttempt.objects.create(...)` for a completed attempt MUST set it
  (Postgres sorts the NULLs first on the default `-completed_at` ordering).
- Backend runs tests via `docker compose exec -T backend pytest`; `head` is
  shadowed locally; frontend node_modules is a container volume.

## Files to read first
- `docs/specs/phase-32-duolingo-quiz-ux.md` (only manual section open)
- `backend/quizzes/views.py` — "Quiz Session Flow (Phase 32)" block
- `backend/courses/views.py` — "Lesson-Check Mastery Sessions (Phase 32)" block
- `backend/gamification/services.py` — `_update_streak` / `_award`
- `frontend/src/components/quiz/QuizSessionFlow.tsx`
