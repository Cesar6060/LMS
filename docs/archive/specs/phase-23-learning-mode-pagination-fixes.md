# Phase 23: Learning-Mode Pagination Fixes

## Goal

Make the already-built lesson pagination + end-of-lesson quiz flow actually
work in learning mode. The `LessonSection` "slide-deck" model, the instructor
Section editor, the player's page-flipping, and the inline comprehension-quiz
gate all exist end to end — but **no lesson uses any of it** (all 14 lessons are
single markdown blobs with no sections and no quiz), so in learning mode every
lesson renders as one scroll with no quiz and pagination never engages. This
phase keeps the existing manual-section model, fixes the correctness bugs that
surface once a lesson *does* have sections and/or a quiz, seeds one real
multi-page + quiz lesson so the feature is visible and testable, and removes
dead code. No new models, endpoints, or routes.

## Decisions made during scoping (from interview)

- **Page model:** Manual sections, as built. Instructors author ordered pages in
  the existing Section editor; content is *not* auto-paginated.
- **Completion quiz:** The **inline comprehension quiz** (`LessonQuizSection`,
  rendered as the lesson's final page) is *the* quiz that completes a lesson.
  Passing it auto-marks the lesson complete.
- **Quiz requirement:** **Optional per lesson.** A lesson with no quiz can be
  marked complete directly; the quiz only gates lessons that actually have one.
  (Matches the existing backend `validate_completed` gating.)
- **Also in scope:** the legacy-content+quiz rendering bug, removing the dead
  `SectionNav` component, auto-advance/resume correctness, and seeding a demo
  lesson.

## Intended behavior (target model)

A lesson in learning mode is an ordered sequence of **pages**:

1. If the lesson has `sections` → each section is a page, in `order`.
2. If the lesson has **no** sections → the legacy `content`/video blob is page 1
   (the fallback page always renders, even when empty).
3. If the lesson has a comprehension quiz (`total_questions > 0`) → the quiz is
   appended as the **final** page.

Therefore:

```
contentPageCount = sections.length > 0 ? sections.length : 1
totalSections    = contentPageCount + (hasQuiz ? 1 : 0)
isOnQuizSection  = hasQuiz && currentSectionIndex === totalSections - 1
```

Completion:
- Lesson **with** a quiz: no manual "Mark Complete"; passing the final-page quiz
  auto-completes the lesson (existing `onComplete` → `handleMarkComplete`).
- Lesson **without** a quiz: "Mark Complete" button on the last page (existing).

## Out of scope

- Auto-pagination / splitting a single markdown blob into pages (rejected in
  scoping — sections stay manual).
- The separate unit-level **`required_quiz`** gate (`required_quiz_info` badges,
  `/courses/:code/quizzes/:id` flow). Leave the existing code untouched; no
  lesson uses it and the completion quiz is the inline one. Do not remove it.
- Any change to the `LessonSection` model, migrations, or the section CRUD /
  reorder endpoints — they already exist and work.
- Instructor Section-editor redesign. We *use* it and verify it works; we don't
  rework its UI beyond bugs that block authoring.
- Mobile/responsive rework, theme/color changes.
- Backfilling sections/quizzes onto all 14 lessons. Only one demo lesson is
  seeded; the rest stay legacy single-page (still valid).

## Backend tasks

No new models, migrations, or endpoints. Work is limited to seed data and tests.

- [x] **Seed a demo multi-page + quiz lesson.** In
      `backend/courses/management/commands/seed_data.py`, extend the seed so one
      existing lesson (e.g. "Variables and Data Types") gets:
  - 2–3 ordered `LessonSection` rows (`lesson`, `title`, `content`, `order`;
    at least one with a `video_type='youtube'` + `video_id` to exercise the
    section-video path).
  - A short comprehension quiz: 2–3 `LessonQuestion` rows with
    `LessonQuestionChoice`s (one correct each), attached to the same lesson.
  - Idempotent: re-running `seed_data` must not duplicate sections/questions
    (guard with `get_or_create` / existence checks, matching the file's existing
    style).
- [x] **Verify section write endpoints stay owner-only.** Confirm (test below)
      that `POST/PUT/DELETE /api/.../lessons/<id>/sections/` and
      `.../sections/reorder/` reject a non-owner (403). No code change expected —
      this is a guard against regressions.
- [x] **Tests** (`backend/courses/tests.py`, pytest):
  - `test_lesson_detail_returns_sections_in_order` — a lesson with 3 sections
    created out of order returns them sorted by `order` in the `LessonSerializer`
    (`GET /api/.../lessons/<id>/`).
  - `test_complete_blocked_until_comprehension_quiz_passed` — for a lesson with
    comprehension questions, `PATCH .../lessons/<id>/progress/ {completed: true}`
    returns 400 while unpassed, and 200 after a passing `LessonQuizAttempt`
    (exercises `LessonProgressUpdateSerializer.validate_completed`).
  - `test_complete_allowed_when_no_quiz` — a lesson with no questions and no
    `required_quiz` can be marked complete directly (200).
  - `test_section_write_requires_course_owner` — a non-owner enrolled student
    gets 403 on section create/reorder.
  - Reuse existing fixtures/factories; check `backend/courses/tests/` for a
    lesson/enrollment factory before writing new setup.

## Frontend tasks

All in `frontend/src/pages/courses/CoursePlayerPage.tsx` unless noted. Anchors
are current line numbers.

- [x] **Fix pagination math so legacy content counts as a page** (fixes the
      "single-blob lesson + quiz shows only the quiz, hiding content" bug).
      Introduce `contentPageCount = contentSections.length > 0 ?
      contentSections.length : 1` and derive from it:
  - `totalSections` (currently `:376-378`) → `contentPageCount + (hasQuiz ? 1 : 0)`.
  - `hasSections` (`:379`) stays `totalSections > 1`.
  - `isOnQuizSection` (`:382`) unchanged in form but now correct because
    `totalSections` is right.
  - `currentSection` (`:383`) — unchanged: still `null` on the legacy path so
    `renderSectionContent()`'s legacy branch (`:463-500`) renders the blob for
    page 0 when there are no sections.
  - `isLastSection` (`:384`) unchanged in form.
      Net effect: a no-sections lesson **with** a quiz becomes 2 pages
      (content, then quiz) instead of 1 quiz-only page.
- [x] **Fix the resume clamp in `loadLesson`** (`:176-187`). Replace
      `contentSectionsCount = lessonData.sections?.length || 0` /
      `maxSectionIndex = contentSectionsCount + (hasQuizSection ? 1 : 0) - 1`
      with the same `contentPageCount` logic (`sections.length || 1`) so a
      resumed `current_section` for a legacy-content+quiz lesson isn't clamped to
      0 when it should allow index 1.
- [x] **Fix `handleSectionChange` max index** (`:222-227`). Same substitution:
      `maxIndex = contentPageCount + (hasQuizSection ? 1 : 0) - 1`.
- [x] **Fix `handleVideoEnded` so a section video never skips the quiz**
      (`:305-349`). Current logic keys off `currentLesson.sections.length` and
      marks the lesson complete when on the last *content* section — bypassing an
      appended quiz page (backend then rejects `completed:true`, leaving the
      student stuck). Change to: if `currentSectionIndex < totalSections - 1`,
      advance one page (`handleSectionChange(currentSectionIndex + 1)`);
      otherwise only auto-complete when on the final page **and** there is no
      quiz gate (`!hasQuiz`). Keep the existing next-lesson auto-advance for the
      genuine last page.
- [x] **Remove dead code:** delete
      `frontend/src/components/lesson/SectionNav.tsx` (referenced nowhere but
      itself — confirmed). Ensure no import/type breaks.
- [x] **Verify footer indicators follow the corrected totals.** The dot row and
      `currentSectionIndex+1/totalSections` counter (`:737-781`) derive from
      `totalSections`/`contentSections`, so they should update automatically —
      confirm the content dots (`contentSections.map`, `:743`) still render one
      dot per content page for the legacy path (0 content dots + 1 quiz square is
      acceptable for a blob+quiz lesson; verify it reads sensibly, adjust only if
      it looks broken).
- [x] **No new types or services.** `LessonSection`, `current_section`,
      `getLessonSections`/`updateLessonProgress`, and the section CRUD services
      already exist and are correct.

## Verification

- [x] `cd backend && pytest` — 196 passed (192 baseline + 4 new tests).
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 errors (24 pre-existing exhaustive-deps warnings, unchanged).
- [x] `/verify-stack` output shown as evidence.
- [x] Re-run `seed_data` twice — 2nd run reported "0 new section(s), 0 new question(s)"; DB has exactly 3 sections (1 youtube) + 3 questions + 12 choices.
- [ ] **Manual flow** (against the running Docker stack, hard-refresh
      localhost:5173):
  1. **Instructor authoring:** open the seeded lesson's editor → **Sections**
     tab → confirm the seeded sections list, add one more section, reorder, save;
     changes persist on reload.
  2. **Student pagination:** enter learning mode on the seeded lesson → flip
     through all pages via footer **Next/Prev**, **←/→ keys**, and the **dot
     indicators**; the `x/total` counter is correct and the section-video page
     plays.
  3. **Quiz as last page → completion:** the comprehension quiz is the **final**
     page; the "Go to Quiz →" shortcut jumps there; passing all questions
     auto-marks the lesson complete and auto-advances to the next lesson; the
     sidebar checkmark updates.
  4. **Legacy-blob + quiz bug fixed:** on a no-sections lesson that has a quiz
     (temporarily add a comprehension question to a legacy lesson, or use the
     seed), page 1 shows the lesson **content** and page 2 is the quiz — content
     is no longer hidden.
  5. **No-quiz lesson:** a legacy single-blob lesson with no quiz still shows the
     **Mark Complete** button on its (only) page and completes directly.
  6. **Video auto-advance:** on a section that has a video, letting it end
     advances to the **next page** (not straight to lesson-complete), and never
     skips the quiz gate.

## Rollout / handoff notes

- Branch from `lms/main` (not the stale `feature/lesson-pagination-and-quiz-section`
  branch, which is 52 commits of divergent history). Cherry-pick nothing from it.
- Conventional commits, no Co-Authored-By lines.
- Update this checklist as items land; run `/handoff` at session end.
