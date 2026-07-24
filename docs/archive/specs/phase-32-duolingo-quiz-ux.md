# Phase 32: Duolingo-Style Quiz UX & Deeper Gamification

Executes ADR-019 Stage 2, scoped down per interview (2026-07-19). **Branch
note:** builds on the unpushed chain — branch from
`feat/phase-31-instructor-analytics` HEAD (or from main once Phases 29–31
merge).

## Goal

Replace the all-questions-on-one-page quiz experience with a
Duolingo-style flow on BOTH quiz systems: one question at a time, instant
right/wrong feedback after each answer locks in, and missed questions
re-queued until every question is answered correctly
(retry-until-mastery). Graded unit quizzes keep grading integrity by
scoring **first-try correctness only**. On top of that: streak freezes
(earned on level-up, auto-applied) and a single mascot character that
reacts inside the quiz flow. The goal is that taking a quiz feels like a
game round, not a test form — while the gradebook, analytics, and XP rules
from Phases 30–31 keep working unchanged.

## Decisions (interview 2026-07-19)

1. **Scope:** Duolingo quiz UX + streak freezes + mascot. Hearts/lives,
   course map/skill tree, and leaderboards are **deferred** (Phase 32b+).
   For the record: when leaderboards do land, names display as
   **first name + last initial** (never email; fallback "Student").
2. **Both quiz systems** get the new flow — lesson comprehension checks
   and graded unit quizzes — via one shared frontend component.
3. **Unit quiz scoring:** missed questions re-queue until mastered, but
   the recorded score = **first-try correctness %**. `passing_score` and
   `max_attempts` (full retakes to improve the score) keep working.
   A session can end "mastered" yet below passing — the completion screen
   must show both clearly.
4. **Lesson checks: attempt cap retired.** Mastery-retry guarantees a
   pass, so `Lesson.max_quiz_attempts` becomes meaningless — new session
   flow ignores it, instructor UI stops offering it. Keep the model field
   (ignored) for painless rollback.
5. **Streak freezes:** earn 1 per level-up, hold max 2, consumed
   automatically when a missed day would break the streak. No currency
   system, no manual arming.
6. **Mascot:** one built-in SVG character ("Circuit" the robot) with a
   few poses, living in the quiz flow's feedback moments plus a small
   dashboard greeting. No selectable characters, no asset pipeline.
7. **XP rules unchanged** from Phase 30: +20 on first-ever pass per
   quiz/check, +50 lesson completion, XPEvent ledger dedupes. The new
   finalize responses embed the same `gamification` delta shape.

## Out of scope

- Hearts/lives, course map / skill tree, leaderboards (and the
  display-name field they'll need).
- New question types (everything stays multiple-choice), shuffle,
  time limits, per-question point weights.
- Removing the legacy batch-submit endpoints (`POST /quizzes/<id>/submit/`,
  `POST lessons/<id>/submit-quiz/`) — they stay functional for rollback;
  only the frontend stops calling them.
- Changing XP amounts, level thresholds, or badge catalog.
- Streak freeze gifting/purchase, streak repair, weekly grants.
- Mascot outside quiz flow + dashboard greeting (no empty states, no
  course pages).
- Instructor-facing changes beyond removing the lesson-check attempt-cap
  input; analytics pages untouched (semantics note below).

## Data model notes

- **Unit quizzes** (`quizzes` app): `QuizAttempt` gains
  `status` (`in_progress` | `completed`, default `completed` so all
  existing rows migrate correctly) and `completed_at` changes from
  `auto_now_add` to nullable, set at finalize. `AttemptAnswer` keeps
  `selected_choice`/`is_correct` as the **first try** (never overwritten
  — this is the score record) and gains `mastered_at` (nullable; stamped
  when the question is eventually answered correctly). Re-queue = questions
  with `mastered_at IS NULL`.
- **Lesson checks** (`courses` app): new `LessonAttemptAnswer` model
  mirroring the above (`attempt` FK to `LessonQuizAttempt`, `question`,
  `selected_choice`, `is_correct` first-try, `mastered_at`;
  `unique_together ['attempt', 'question']`). `LessonQuizAttempt` gains
  `status` + nullable `completed_at` the same way. **Semantics shift,
  documented:** `score` now records first-try correct count and `passed`
  means "session completed via mastery" — Phase 31 analytics keeps
  working; its lesson-check avg% becomes a first-try-difficulty signal
  and pass-rate trends toward "completed the check". Legacy
  `LessonQuestionAnswer` (latest-answer-per-user) still gets updated on
  every graded answer so `questions-status` and existing UI contracts
  hold.
- **Gamification:** `GameProfile` gains `streak_freezes`
  (PositiveSmallInteger, default 0, cap 2).

## Backend tasks

### quizzes app — session flow

- [x] Migration: `QuizAttempt.status` (default `completed`),
      `completed_at` → `null=True` (backfill untouched — existing rows
      already have values); `AttemptAnswer.mastered_at`.
- [x] `POST /api/quizzes/<quiz_id>/session/start/` — student-only,
      enrolled (same access check as `submit_quiz`). Returns the existing
      in-progress attempt if one exists (resume), else creates one.
      Enforces `max_attempts` against **completed** attempts only. 400 if
      quiz has no questions.
- [x] `GET /api/quizzes/<quiz_id>/session/` — resume state: attempt id,
      per-question `{answered, first_try_correct, mastered}`, ordered
      remaining-question ids (unmastered, original order then re-queue
      order), counts. 404 if no in-progress attempt.
- [x] `POST /api/quizzes/<quiz_id>/session/answer/` — body
      `{question_id, choice_id}`. Server-side grade; first answer for a
      question writes `AttemptAnswer` (first-try record), correct answers
      (first or retry) stamp `mastered_at`. Response:
      `{is_correct, correct_choice_id, correct_choice_text,
      remaining_count, session_complete}`. Rejects questions not in the
      quiz, already-mastered questions, and completed attempts (400).
- [x] **Auto-finalize** inside `answer` when the last question masters:
      compute `score` from first-try `is_correct` (same formula as
      `submit_quiz`), set `passed`, `status=completed`, `completed_at`;
      on pass call `award_quiz_pass`; response additionally carries the
      full attempt result + `gamification` delta (same shape as
      `submit_quiz` response so the frontend result screen is shared).
- [x] Filter **every** consumer of attempts to `status='completed'`:
      `get_best_score` / `attempts_remaining` in both serializers,
      attempt-history endpoint, `quick_grade_quiz` (most-recent completed),
      gradebook queries in `courses` (grep for `QuizAttempt` — Phase 31
      analytics `_analytics_student_rows` included), enhanced dashboard.
- [x] Legacy `submit_quiz` untouched and still passing its tests.
- [x] Tests (`quizzes/tests.py`): permission boundary (unauth 401,
      instructor 403, unenrolled student 403) on all three routes; start
      respects max_attempts (completed-only — an abandoned in-progress
      attempt does NOT burn one); resume returns same attempt; first-try
      wrong then correct → mastered but scored 0 for that question;
      score/passed math on finalize; mastered-below-passing case
      (`passed=False`, retake allowed); XP awarded once on pass, not on
      re-pass; legacy submit still green; best-score/gradebook ignore
      in-progress rows.

### courses app — lesson-check session flow

- [x] Migration: `LessonAttemptAnswer`; `LessonQuizAttempt.status` +
      nullable `completed_at` (default/backfill as above).
- [x] `POST /api/.../lessons/<lesson_id>/quiz-session/start/`,
      `GET .../quiz-session/`, `POST .../quiz-session/answer/` —
      mirror the quizzes endpoints (enrollment check via
      `require_course_access`). **Ignore `max_quiz_attempts` entirely.**
      `attempt_number` still increments per completed session.
- [x] Auto-finalize when all mastered: `score` = first-try correct count,
      `passed=True`, stamp `completed_at`; call `award_lesson_quiz_pass`;
      response includes `can_complete_lesson: true` + `gamification`
      delta. Also update legacy `LessonQuestionAnswer` rows on every
      graded answer (latest answer) so `questions-status` and
      `can_complete_lesson` gating stay consistent.
- [x] `lesson_questions_status` reports `attempts_remaining: null` /
      `can_attempt: true` under the new model (cap retired) without
      breaking its response contract for old clients.
- [x] Filter lesson-check consumers to completed attempts (Phase 31
      analytics, gradebook lesson-completion math, `questions-status`
      `has_passed`).
- [x] Tests (`courses/tests.py`): boundary trio on all three routes;
      mastery loop (wrong → re-queue → correct → finalize passed);
      first-try score recorded; cap ignored (session allowed with
      max_quiz_attempts=1 and a prior completed attempt); lesson
      completion unblocks after mastery; XP once; legacy submit-quiz and
      questions-status still green.

### gamification app — streak freezes

- [x] Migration: `GameProfile.streak_freezes` (default 0).
- [x] `_award()`: on `leveled_up`, +1 freeze per level gained, capped at
      2; surface `freezes_earned` in `GamificationResult`/`as_dict`.
- [x] `_update_streak()`: gap of N missed days — if
      `0 < missed_days <= streak_freezes`, consume that many freezes and
      continue the streak (+1 for today); else reset to 1 and consume
      nothing. Surface `freezes_used` in the result. Same lazy,
      user-timezone evaluation as today.
- [x] `profile_payload()` adds `streak_freezes`.
- [x] Tests: earn on level-up capped at 2; 1-day gap with a freeze →
      streak continues, freeze consumed; 2-day gap with 1 freeze → reset,
      freeze kept; multi-level jump grants respect cap; instructor still
      inert; backfill command unaffected.

## Frontend tasks

- [x] Types (`types/index.ts`): `QuizSessionState`, `SessionAnswerResult`
      (+ lesson-check variants if shapes differ), `streak_freezes` +
      `freezes_earned`/`freezes_used` on gamification types.
- [x] Services: `quizzes.ts` — `startQuizSession`, `getQuizSession`,
      `answerQuizQuestion`; `courses.ts` — lesson-check equivalents.
- [x] **`components/quiz/QuizSessionFlow.tsx`** — the shared Duolingo
      flow used by both systems (parametrized by the three service
      calls + question list): top progress bar (mastered/total), one
      question card at a time, large real-button choices (per UI
      readability prefs: big type, generous targets), "Check" locks in →
      full-width green/red feedback banner with correct answer on miss +
      mascot pose → "Continue" → next or re-queued question → completion
      screen. Resumes an in-progress session on mount via GET. Keyboard:
      1–4 select, Enter check/continue.
- [x] Completion screens: lesson check — "Mastered!" + mark-complete
      handoff (existing `onComplete` path); unit quiz — first-try score
      vs `passing_score`, pass/fail prominently, "Retake" only when
      failed and attempts remain, then the existing answer-review list.
      Both fire `useGamificationFeedback` with the returned delta.
- [x] `pages/quizzes/QuizDetailPage.tsx`: keep intro screen (add "resume
      in-progress attempt" state when GET session hits), swap the
      questions form for `QuizSessionFlow`.
- [x] `components/lesson/LessonQuizSection.tsx`: swap batch flow for
      `QuizSessionFlow`; remove attempts-remaining UI. Delete
      `components/lesson/LessonQuestions.tsx` if confirmed unused (grep
      imports first).
- [x] Instructor: remove the max-attempts input from the lesson editor
      UI (field stays server-side, ignored); quiz editor untouched.
- [x] **`components/gamification/Mascot.tsx`** — inline SVG "Circuit"
      robot, `pose` prop: `idle | cheer | encourage | celebrate`;
      theme-aware colors; used in the feedback banner, completion
      screens, and a small dashboard greeting line (`DashboardPage`).
      CSS-only animation (bounce/wiggle), no library.
- [x] Streak freeze display: 🧊×N chip next to `StreakFlame` on dashboard
      and Settings→Achievements; toast via `useGamificationFeedback` for
      "Streak freeze earned!" (`freezes_earned`) and "Streak freeze used —
      streak saved!" (`freezes_used`).
- [x] `npm install` nothing new expected; if anything is added, install in
      the container too (node_modules is a container volume).

## Verification

- [x] `docker compose exec -T backend pytest` — all green including the
      new session/freeze tests AND the untouched legacy submit tests
      (target: Phase 31 baseline 276 + new).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `npm run lint` — no new errors/warnings vs 25-warning baseline.
- [x] `/verify-stack` output shown as evidence.
- [ ] Manual click-through (seeded course, student account):
  - [ ] Unit quiz: start → one question at a time → wrong answer shows
        red banner + correct answer + encourage mascot → question returns
        later → correct on retry shows cheer → completion shows first-try
        score; a mastered-but-failed run offers Retake; reload mid-session
        resumes at the right question; abandoned session doesn't consume
        an attempt (check attempts-remaining on intro).
  - [ ] Lesson check: mastery loop ends in pass regardless of misses;
        lesson becomes completable; +XP toast once; no attempts-remaining
        anywhere; re-entering a passed check offers practice/retake
        without changing gradebook lesson state.
  - [ ] Streak freeze: level up → "freeze earned" toast, 🧊×1 on
        dashboard; (via backdated `last_activity_date` in dbshell)
        1-day gap + freeze → streak survives with "freeze used" toast;
        2-day gap + 1 freeze → streak resets, freeze kept.
  - [ ] Mascot renders in both themes, poses switch, dashboard greeting
        shows; instructor sees none of the gamification UI.
  - [ ] Instructor: lesson editor no longer shows max-attempts; Phase 31
        analytics page still loads with sane lesson-check numbers.
  - [ ] Permission spot-check: instructor and unenrolled student get 403
        on a session start (curl or devtools).
