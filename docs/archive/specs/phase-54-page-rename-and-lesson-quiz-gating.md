# Phase 54 — "Page" rename + lesson quiz-gating simplification

## Goal

Two UX problems surfaced by the user after reviewing the live lesson editor
(post Phase 53):

1. **"Section" is the wrong word.** A lesson is made of *pages*; the editor
   should read as "all the pages of this lesson." Rename **"Section" → "Page"**
   everywhere user-facing (instructor editor + student player). This is a
   **presentation-layer rename only** — the backend model stays `LessonSection`
   (a full model rename is a large migration for zero functional gain).

2. **Quiz gating is confusing and doubled.** A lesson today has **two
   independent completion gates**, both enforced in
   `LessonProgressUpdateSerializer.validate_completed`:
   - **System A — `Lesson.required_quiz`** (FK → the external `quizzes.Quiz`
     app). Surfaced in the editor's **"Details" tab** as a dropdown of *every
     quiz in the whole course* (quizzes belonging to other lessons/units). The
     instructor picks an unrelated course quiz as this lesson's gate. This is the
     main source of confusion.
   - **System B — the lesson's own comprehension questions** (`LessonQuestion`,
     the Phase-32 mastery flow, authored in the **"Questions" tab**). This
     already gates per-lesson, but *implicitly and unconditionally*: the moment a
     lesson has ≥1 question, the student must pass them to complete — there's no
     way to author ungated practice questions, and no `passing_score` /
     threshold field (threshold is implicitly 100% mastery).

   This phase makes **System B the single gate** and gives it an explicit
   per-lesson toggle. System A's cross-course dropdown is removed; the
   `required_quiz` FK is cleared and stops gating (column kept dormant, mirroring
   Phase 53's low-risk approach). The near-useless **"Details" tab is dropped**
   (its only remaining fields were Title — already in the header — and the
   Required Quiz dropdown being removed); the lesson title becomes editable
   inline in the header, and the new require-quiz toggle lives atop the
   **"Questions" tab**, its natural home.

### End state

- Instructor tabs: **Content · Questions · Attachments** (no Details).
- Lesson title: click-to-edit inline in the header, auto-saves.
- "Questions" tab has a prominent toggle: **"Require students to pass this
  lesson's quiz to complete it."**
  - **ON** → the lesson's own questions gate completion (today's behavior).
  - **OFF** → questions are optional practice: students can still take them, but
    they don't block completion.
- No cross-course "Required Quiz" dropdown anywhere. No external `quizzes.Quiz`
  involved in lesson completion.
- Every user-facing "Section" reads "Page".

## Out of scope

- Renaming the backend `LessonSection` model / DB table / API routes / internal
  variable & comment names (`currentSectionIndex`, `contentSection`, etc.). UI
  copy only.
- Dropping the dormant `required_quiz` / `max_quiz_attempts` columns (kept
  dormant; a future phase may remove them).
- Per-question or per-lesson **passing threshold / partial mastery** (stays
  implicit 100%-correct; no new threshold field).
- Reworking the Phase-32 mastery *session* mechanics (start/answer/finalize XP),
  the standalone `quizzes.Quiz` app itself, or unit-level quizzes.
- A dedicated "practice questions" surface beyond the existing in-player quiz
  page (OFF simply means "not required"; the same quiz page is reused).
- Phase 52 deploy debt (separate reminder).

## Key decisions (from scoping interview)

1. **Gate model = lesson's own questions only.** Remove System A's cross-course
   `required_quiz` dropdown. Completion gates only on System B.
2. **Explicit toggle** — new `Lesson.requires_quiz` boolean. ON = questions gate;
   OFF = optional practice. Migration seeds it: `requires_quiz=True` for lessons
   that currently have ≥1 question (preserve today's behavior), else `False`.
3. **Drop the Details tab.** Title becomes inline click-to-edit in the header
   (auto-save, reuse existing debounce infra). Toggle lives in the Questions tab.
4. **Clear + stop enforcing System A.** Data migration nulls `required_quiz` on
   all lessons; remove its branch from `validate_completed`. Column kept dormant
   (no DDL drop). Because the field is no longer writable from the API, the
   Phase-53 `LessonQuizScopeMixin` IDOR fix becomes moot and its now-dead code is
   removed with it.
5. **"Section" → "Page"** is a presentation-layer rename; model stays
   `LessonSection`.

## Backend tasks

- [x] **Migration `backend/courses/migrations/0020_lesson_requires_quiz.py`**
      (confirm `0020` is next). Inside `transaction.atomic()`:
      - `AddField` `requires_quiz = BooleanField(default=False)` on `Lesson`.
      - `RunPython` forward (historical models via `apps.get_model`):
        - Set `requires_quiz=True` for every lesson where `questions.exists()`
          (preserves the current "any question gates" behavior).
        - Set `required_quiz=None` for **all** lessons (retire System A gates).
        - Print a summary: `[0020] N lessons → requires_quiz=True, M required_quiz
          values cleared`.
      - Reverse = `migrations.RunPython.noop` for the data step (the AddField
        reverses normally). One-way data retirement; cleared FK values are not
        reconstructable.
- [x] Run **`db-migration-checker`** on `0020` before merge (expect: one additive
      column with a default + data-only RunPython, reversible AddField,
      noop-reverse data, no destructive drop). Record the verdict in this spec.
- [x] `[P]` **Migration tests** (`backend/courses/tests.py`):
      - Lesson with ≥1 `LessonQuestion` → `requires_quiz` becomes `True`.
      - Lesson with 0 questions → `requires_quiz` stays `False`.
      - Lesson with a `required_quiz` FK set → cleared to `None` after migration.
- [x] **`backend/courses/serializers.py` — completion gate**
      (`LessonProgressUpdateSerializer.validate_completed`, ~lines 474–501):
      - **Remove** the System-A `required_quiz` branch entirely (was ~490–501).
      - **Change** the System-B branch (~474–487) to gate only when
        `lesson.requires_quiz and lesson.questions.exists()` (today it's
        `lesson.questions.count() > 0`). Keep the existing
        `LessonQuizAttempt(passed=True)` check as the pass condition.
- [x] **`backend/courses/serializers.py` — surfacing & write fields:**
      - Add `requires_quiz` (writable) to the lesson serializers used by the
        editor (`LessonSerializer` / `LessonCreateSerializer` as applicable) and
        expose it read-side wherever `question_count` is exposed.
      - **Remove** `required_quiz` from writable serializers and remove the now-
        dead `required_quiz_info` / `required_quiz_passed` read fields
        (`LessonProgressSerializer`, `LessonListSerializer`, `LessonDetailSerializer`
        — ~lines 170–175, 216–221, 411–433) and `validate_required_quiz` /
        `LessonQuizScopeMixin` (Phase-53 IDOR fix — moot once the field isn't
        writable). Grep for every reader before deleting.
      - Keep the `required_quiz` **model column** dormant (no migration drop).
- [x] **`backend/courses/views.py` — align the "can complete" status with the
      gate** (fixes an inconsistency found while scoping). Three definitions of
      "can complete lesson" currently disagree:
      - `can_complete_lesson` endpoint (~`views.py:2254`) = `has_passed or
        all_correct` (legacy `LessonQuestionAnswer`).
      - `validate_completed` (the real gate) requires a passing `LessonQuizAttempt`.
      - `LessonProgressSerializer.get_lesson_questions_status.can_complete_lesson`
        (~`serializers.py:435–458`) = `all_correct` only.
      Make all three agree with the new gate: **not required** (`requires_quiz`
      False or no questions) ⇒ can complete; **required** ⇒ can complete iff a
      passing `LessonQuizAttempt` exists. This prevents the UI showing "ready to
      complete" while the save 400s.
- [x] `[P]` **Gate tests** (`backend/courses/tests.py`): student cannot complete
      a `requires_quiz=True` lesson without a passing `LessonQuizAttempt`; **can**
      complete when `requires_quiz=False` even with unpassed questions; toggling
      `requires_quiz` off unblocks completion; setting a `required_quiz` FK via
      the API is rejected/ignored (field no longer writable).

## Frontend tasks

### Rename "Section" → "Page" (presentation only)

- [x] **`frontend/src/components/lesson/SectionEditor.tsx`** — visible strings:
      `"Add Section"`/`"Edit Section"` (266, 382), `"Section {index+1}"`
      (334, 572), `"Paste to add sections"` (262, 292, 514) → "Paste to add
      pages", `"Create a new section for this lesson."` (387), placeholder
      `"Write section content using Markdown…"` (463), `"Failed to add sections"`
      (243), `"…produced no sections."` (560), `title="Remove this section"`
      (585), and the empty-state copy. → all "Page(s)".
- [x] **`frontend/src/pages/courses/CoursePlayerPage.tsx`** — student-facing:
      dot tooltip `` title={`Section ${i + 1}`} `` (788) → `` `Page ${i + 1}` ``;
      `"No content available for this section."` (555) → "…for this page."; any
      other visible "section" text in the player empty state.
- [x] Grep sweep `grep -rniE 'section' frontend/src --include=*.tsx` filtered to
      JSX text / string literals / `title=`/`placeholder=`/`aria-*` to confirm no
      user-facing "Section" remains. (CourseSidebar / OutlineUnitCard confirmed
      to have **no** user-facing "section" text — nothing to change there.)

### Quiz gating + Details-tab removal

- [x] **`frontend/src/pages/instructor/LessonEditorPage.tsx`:**
      - Remove the **Details** `TabsTrigger`/`TabsContent` and the Required Quiz
        `<select>` + `quizzes` state + `quizzesService.getCourseQuizzes` fetch +
        `required_quiz` from `LessonDetailsForm` / `saveDetails`.
      - Make the header title **click-to-edit inline** (auto-save via the existing
        debounced `saveDetails` → `courseService.updateLesson({ title })`). Keep
        the header save-status indicator and the `beforeunload` leave-guard.
      - Tabs become `defaultValue="content"` → **Content · Questions ·
        Attachments**.
- [x] **`frontend/src/components/lesson/LessonQuestionsManager.tsx`:**
      - Add a prominent toggle at the top: **"Require students to pass this
        lesson's quiz to complete it"** (readable label + helper text per the UI
        readability prefs, not tiny grey). Wire to
        `courseService.updateLesson(lessonId, { requires_quiz })`; reflect the
        lesson's current value. Auto-save; surface save state consistently.
      - Update the standing copy line (~192) "Students must answer all questions
        correctly to complete the lesson." to be conditional on the toggle
        (required vs optional-practice wording).
- [x] **`frontend/src/pages/courses/CoursePlayerPage.tsx` — gate rendering:**
      - **Remove** the System-A required-quiz badge + "Take Quiz" off-player link
        (~655–682) and the `required_quiz_info` suppression of Mark Complete
        (~714). (`required_quiz_info` is now always null.)
      - **Split render from gate** (per code-review Finding 1): `hasQuiz`
        (= `total_questions > 0`) means the lesson has a comprehension-quiz PAGE,
        always rendered so students can take it; `quizGates`
        (= `hasQuiz && requires_quiz`) means passing is REQUIRED to complete.
        All page-count / nav / resume derivations key off `hasQuiz`; completion
        gating keys off `quizGates`. So when `requires_quiz` is OFF the questions
        remain reachable as optional practice, and Mark Complete stays available
        on the last page.
      - Gate the Mark Complete button on `!quizGates`; the "must pass" badge and
        the alternate "Lesson Completed" indicator show only when `quizGates`.
- [x] **`frontend/src/types/index.ts` + `frontend/src/services/courses.ts`:** add
      `requires_quiz: boolean` to the `Lesson` type and `updateLesson` payload;
      drop `required_quiz` / `required_quiz_info` / `required_quiz_passed` from
      the types once no reader remains (tsc will enforce).

## Verification & review

- [x] `db-migration-checker` on `0020` — **SAFE-WITH-NOTES**. DDL is additive
      (metadata-only column add; AlterField is a no-op). One rollout note: the
      data step nulls `required_quiz` on all lessons, so it retires the live
      System-A gate; apply it close to merge and dump existing `required_quiz`
      values first (noop reverse = one-way). Dev had **0** such values.
- [x] `code-reviewer` — **REQUEST-CHANGES on Finding 1** (OFF hid the questions
      instead of leaving them as optional practice); **fixed** via the
      render/gate split above. Findings 2–4 non-blocking (dead course-map FK
      reader kept dormant; `has_passed` type made optional; checklist updated).
- [x] `adversarial-tester` — **30/30 probes held, no BROKEN**. One SUSPICIOUS
      (gate didn't filter `LessonQuizAttempt.status`) **hardened**: both the gate
      and the status serializer now require `status=STATUS_COMPLETED`. Added
      regression tests (cross-user, in-progress attempt, cross-course IDOR).
- [x] `/verify-stack` (post-fix) — pytest **503 passed**, `tsc --noEmit`
      **0 errors**, lint **0**.
- [ ] Manual click-through (instructor): title inline edit saves; toggle on/off;
      no Details tab. (Student): required lesson blocks until passed; optional
      lesson completes freely; player says "Page N".

## Deploy (the real action for this phase)

- [ ] Apply `0020` to Neon (additive column + data backfill; safe to migrate
      before merge): `DATABASE_URL=<neon> python manage.py migrate courses` —
      capture the `[0020] …` summary line.
- [ ] Merge the PR (remote **`lms`** / Cesar6060/LMS); let Render + Cloudflare
      Pages auto-deploy.
- [ ] Post-deploy spot-check: a required lesson blocks completion until passed; a
      lesson with the toggle off completes freely; editor shows no Details tab and
      inline-editable title; `https://stemquest-api-va.onrender.com/api/health/?deep=1`.

## Files to read first

- `frontend/src/pages/instructor/LessonEditorPage.tsx` — Details tab + required_quiz select.
- `frontend/src/components/lesson/LessonQuestionsManager.tsx` — new toggle home.
- `frontend/src/pages/courses/CoursePlayerPage.tsx` — both gates render here (~655–732).
- `backend/courses/serializers.py` — `validate_completed` (~474–501), required_quiz surfacing.
- `backend/courses/views.py` — `can_complete_lesson` (~2254), `start_lesson_quiz_session`.
- `backend/courses/models.py` — `Lesson.required_quiz` (110), `max_quiz_attempts` (118), `LessonQuestion` (370).
