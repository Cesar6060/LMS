# Phase 53 — Lesson Content Consolidation (Sections as the single content model)

## Goal

Instructors edit lesson content in a confusing, unreliable way: a lesson has
**two parallel content stores** — a top-level "Content" tab (one markdown body +
one video) *and* a "Sections" tab (many sections, each with its own markdown +
video). The student player silently shadows one with the other: **the moment a
lesson has any sections, the Content-tab markdown and video are never rendered
to students** (`CoursePlayerPage.tsx:408-416`, legacy branch at `:496-533` is
unreachable once `sections.length > 0`). So an instructor adds a video on the
Content tab, hits Save (it *does* persist server-side), and it never appears —
the reported "I added a video and it didn't add it." The single top **Save**
button compounds the confusion: it only saves the Content tab, while
Sections/Questions/Attachments auto-save through their own API calls, so editing
a section never lights up Save and the page feels inert.

This phase makes **Sections the single source of truth for lesson body content**.
Every content-bearing lesson's body becomes an ordered list of sections (one
section = one page: title + markdown + one optional YouTube video). A data
migration converts existing lesson-level content into a first section (and
discards leftover, already-hidden lesson-level content on lessons that already
have sections). The editor is reorganized so the section list *is* the primary
"Content" tab (default, renamed), lesson metadata (Title, Required Quiz) moves to
a "Details" tab, the misleading global Save button is removed, and everything
auto-saves with a visible status indicator. The student player and sidebar stop
reading lesson-level content/video entirely. The old lesson-level columns are
**kept dormant** (no destructive schema change) to keep the Neon migration
low-risk.

## Out of scope

- Deploying Phase 52 (Neon migrations `0017`/`0018` + prod spot-check). Tracked
  separately as a reminder; NOT part of this phase.
- Richer section content: multiple videos/media blocks per section, inline
  images/attachments. Sections stay **title + markdown + one YouTube video**.
- Dropping the lesson-level `content`/`video_type`/`video_id` columns (decision:
  keep dormant; a future phase may remove them).
- The YouTube extraction/validation contract (Phase 52 — `backend/courses/video.py`,
  `frontend/src/lib/video.ts`, `YouTubeVideoPreview.tsx`). Reused as-is.
- Video progress tracking / the YT IFrame player itself.
- Questions and Attachments tabs (behavior unchanged; they already auto-save).

## Key decisions (from scoping interview)

1. **Sections are the sole content model.** Content tab loses its markdown/video;
   they live in sections.
2. **Migration of existing content:** lessons with lesson-level content and **no
   sections** → convert into one section (order 0), preserving what students see.
   Lessons that **already have sections** → discard the leftover (already-hidden)
   lesson-level content by blanking the fields. Reverse migration = noop.
3. **Keep lesson content columns dormant** — no schema drop. Data-only migration.
4. **Auto-save + status** — remove the global Save button; each part auto-saves
   with a visible "All changes saved / Saving… / Couldn't save" indicator.
5. **Tab rename + reorder** — Sections tab → **"Content"**, made the default tab;
   old Content tab → **"Details"** (Title + Required Quiz + max attempts).
6. Sections stay simple: title + markdown + one optional YouTube video.

## Backend tasks

- [x] **Data migration** `backend/courses/migrations/0019_consolidate_lesson_content_into_sections.py`
      (confirm `0019` is the next number). Forward, inside `transaction.atomic()`,
      iterate all `Lesson` rows:
      - If the lesson has **no** sections AND (`content` non-empty OR
        (`video_type == 'youtube'` AND `video_id` non-empty)): create one
        `LessonSection(lesson=..., order=0, title='', content=lesson.content,
        video_type=lesson.video_type, video_id=lesson.video_id)`. Use a blank
        section title (the lesson title is shown elsewhere; avoid a duplicate
        heading).
      - Then, for **every** lesson (both branches), blank the now-dormant
        lesson-level fields: `content=''`, `video_type='none'`, `video_id=''`.
        (Lessons that already had sections thereby discard their hidden content;
        lessons just converted have their content safely copied into the section
        first.)
      - Print a summary: number of lessons converted-to-section, number blanked,
        number skipped (no content, no sections).
      - Use the historical model via `apps.get_model('courses', 'LessonSection')`
        — no import of `courses.video` needed (values are copied verbatim; they
        were already extracted/normalized by Phase 52).
      - Reverse migration = `migrations.RunPython.noop` (one-way data move; the
        original lesson-level content is intentionally not reconstructable).
- [x] Run the **`db-migration-checker`** agent on `0019` before merge (confirm:
      data-only, reversible-noop declared, no schema/DDL change, no destructive
      drop, batched/atomic). **Verdict: SAFE** — pure RunPython, copy-before-blank
      ordering confirmed, no DDL, no section-data loss, correct dependency chain.
- [x] `[P]` **Migration tests** (`backend/courses/tests.py`) using a migration
      test harness or a direct data-shape test that exercises the forward logic:
      - Lesson with `content` + `youtube` video and **no** sections → exactly one
        section created at `order=0` with that content/video; lesson fields blanked.
      - Lesson with existing section(s) + leftover lesson-level content → sections
        untouched (count + contents unchanged); lesson fields blanked; **no** new
        section created.
      - Lesson with no content, no video, no sections → no section created, no error.
      - Lesson with only lesson-level video (empty content) → section created
        carrying the video, empty content.
- [x] Kept the lesson serializers' `content`/`video_type`/`video_id` fields
      (dormant); the editor stops sending them. Added a lightweight `has_video`
      SerializerMethodField (sections-based) to `LessonSerializer` **and**
      `LessonListSerializer` so the sidebar can show a video icon without the
      full `sections` payload. `sections` stays `read_only` on the lesson. No
      code path requires lesson-level content.
- [~] `[P]` **Low-risk hardening — not needed.** The spec suspected
      `lesson_section_detail` PUT (no `partial=True`) could blank omitted fields.
      Adversarial testing showed it does NOT: DRF doesn't copy the model's
      `default=` onto the auto-generated serializer field, so omitted optional
      fields are simply excluded from `validated_data` and left untouched. The
      original risk note was over-stated; left unchanged.
- [x] **Security fix (from adversarial review): cross-course `required_quiz`
      IDOR.** `required_quiz` was a bare `PrimaryKeyRelatedField` over all quizzes,
      letting an instructor gate a lesson on another course's quiz via the API.
      Added `LessonQuizScopeMixin.validate_required_quiz` (applied to
      `LessonSerializer` + `LessonCreateSerializer`) constraining the quiz to the
      lesson's own course (from the instance on update, from the URL `unit_id` on
      create). Regression tests in `TestRequiredQuizCourseScope`.

## Frontend tasks

- [x] **`frontend/src/pages/instructor/LessonEditorPage.tsx`** — reorganize:
      - Rename the **Sections** tab to **"Content"** and make it the **default**
        tab (`defaultValue`). Rename the old **Content** tab to **"Details"**.
      - **Details tab** keeps only: Lesson Title + Required Quiz. Removed the
        Video Type select, YouTube URL input, `YouTubeVideoPreview`, and the
        Markdown editor/preview. **Note:** `max_quiz_attempts` was initially added
        here but removed after adversarial review found it's a dead control — the
        current student mastery-quiz flow (Phase 32) doesn't enforce the cap, so a
        "max attempts" field would mislead instructors. Not surfaced.
      - **Removed the global top "Save" button** and its `isDirty`-gated logic.
        Replaced with **auto-save**: Title / Required Quiz persist via
        `courseService.updateLesson` on an 800ms debounce; removed the
        `extractYouTubeVideoId` call from the old save handler.
      - Add a **global save-status indicator** in the header area: "All changes
        saved" / "Saving…" / "Couldn't save — retry" (real, readable text per the
        UI readability preferences — not tiny grey text). It reflects the most
        recent auto-save across Details + Content(sections).
      - Keep the `beforeunload` / leave-guard, but base it on "a save is in
        flight or last save failed" rather than a Content-tab dirty diff.
- [x] **`frontend/src/components/lesson/SectionEditor.tsx`** — this is now the
      primary "Content" editor:
      - Surface **auto-save status** for section create/update/reorder/delete
        (it already calls the API immediately per action). Emit state up to the
        page-level indicator (callback prop) OR render its own inline
        "Saving…/Saved/Couldn't save" per action. Errors must be visible, not
        swallowed.
      - Strong **empty state**: when a lesson has zero sections, show a prominent
        "Add your first section" call-to-action (big button per UI prefs), making
        clear that sections are where lesson content lives now.
      - Keep the modal editor (title + markdown + one YouTube video with
        `YouTubeVideoPreview` + validation from Phase 52). No new block types.
      - Keep reorder + bulk "paste to add sections" as-is; ensure their results
        also update the save-status indicator.
- [x] `[P]` **`frontend/src/pages/courses/CoursePlayerPage.tsx`** — stop rendering
      lesson-level content/video (path corrected — file is under `pages/courses/`):
      - `contentPageCount` = `contentSections.length` (drop the `hasContentSections
        ? … : 1` fallback at `:408`).
      - Remove/retire the legacy branch (`:496-533`) that renders
        `currentLesson.video_id` / `currentLesson.content`. Render only sections.
      - **Handle a lesson with zero sections gracefully**: if there are no
        sections, show a clear empty state (e.g. "No content yet") and, if a
        `required_quiz` exists, allow proceeding to the quiz. Do not crash on
        `contentSections[0]` being undefined; verify section index / progress
        resume logic (`current_section`) tolerates an empty list.
- [x] `[P]` **`frontend/src/components/course/CourseSidebar.tsx`** — the per-lesson
      "has video" icon (`:192`) currently checks lesson-level
      `video_type`/`video_id`. Change it to reflect whether **any section** has a
      video (`lesson.sections?.some(s => s.video_type === 'youtube' && s.video_id)`),
      falling back to `false` when sections aren't loaded. Confirm the sidebar's
      lesson payload includes `sections` (nested read-only on `LessonSerializer`);
      if the list endpoint uses a lighter serializer without sections, either
      include a `has_video` flag or keep the icon logic tolerant.
- [x] `[P]` **`frontend/src/types/index.ts`** — mark lesson-level `content`,
      `video_type`, `video_id` on `Lesson` as deprecated/optional (keep them so
      the type still matches the API), and ensure `sections` is the documented
      content source. No change to `LessonSection`.
- [x] Confirmed `frontend/src/services/courses.ts` needs **no new endpoints**:
      `updateLesson` (PATCH) still handles Details; section CRUD/reorder/bulk
      endpoints are unchanged.
- [x] Grep sweep done: editor Details no longer edits `content`/`video_*`; player
      no longer renders lesson-level `content`/`video_id`; sidebar uses `has_video`.
      No component renders lesson-level content anymore.

## Verification

- [x] `/verify-stack` passes: backend pytest **493 passed**, `npx tsc --noEmit`
      **0 errors**, `npm run lint` **0 errors/warnings**.
- [x] **Migration proof:** 4 new pytest cases in
      `TestConsolidateContentIntoSectionsMigration` (all pass) + a live local apply:
      `[0019] ... 6 converted to a first section, 6 lesson-level fields blanked, 0
      untouched`. Shell dump confirms no-section lessons became one-section lessons
      carrying their content, and the multi-section "Hello World" lesson kept its 4
      sections while its lesson-level fields were blanked.
- [ ] **Manual flow — reliability (local):** as instructor, open a lesson, go to
      the **Content** tab, add a section with a `youtube.com/shorts/...` URL →
      preview thumbnail appears → status shows "Saving…" then "All changes saved"
      → open the lesson as a student → the video plays. *(Browser click-through
      not run by me — logic verified via tests + data; user to confirm in-app.)*
- [x] **The original bug is gone through the app:** there is no longer any
      lesson-level video/markdown field in the editor; video/content live only in
      sections, and the player renders only sections — so via the UI a video can no
      longer be entered somewhere that silently fails to appear. (Verified in code
      + the migrated data: the screenshot's "Hello World" lesson's dormant fields
      are blanked and its 4 sections are intact.) **Caveat:** the dormant columns
      are intentionally kept (spec out-of-scope to drop them), so a *raw API*
      client can still PATCH `content`/`video_id` onto a lesson — it just won't
      render. Dropping the columns is a possible future phase.
- [ ] **Manual flow — Details auto-save / empty lesson / reorder / sidebar icon:**
      click-throughs left for the user to confirm in-app. Underlying logic is
      covered by tsc + the section/serializer tests; auto-save + status wiring is
      code-reviewed but not browser-clicked by me.
- [x] Deploy order (gotcha from prior phases): migration `0019` applied cleanly to
      the LOCAL dev DB. For prod it is **data-only + reversible-noop** with the old
      columns kept, so old code tolerates the migrated data — safe to
      migrate-before-merge on Neon. **Neon apply is still pending (user action).**

## Notes for implementer

- Backend changes need `docker compose restart backend`; pytest/tsc/lint run
  **inside** the containers (`docker compose exec -T backend pytest`, etc.) — no
  host pytest. Frontend container `node_modules` has been stale before; run
  `docker compose exec -T frontend npm install` if tsc reports missing modules.
- Push/PR remote is **`lms`** (Cesar6060/LMS); `origin` is the archived repo.
  `gh` has no default repo — pass `--repo Cesar6060/LMS`.
- Reuse Phase 52's extraction + `YouTubeVideoPreview`; do not reintroduce a
  duplicate extractor. `frontend/src/lib/video.ts` returns `null` on failure.
- `LessonSection.video_id` is `max_length=100`; only the extracted 11-char ID is
  stored. Leave lengths alone.
- The `[P]`-marked items (migration tests, CoursePlayerPage, CourseSidebar,
  types) touch different files with no shared state and may go to parallel
  subagents. The editor reorg (LessonEditorPage + SectionEditor) is one coupled
  unit; the data migration must exist before its tests run.

## Finish-phase review (2026-07-23)

Two review agents ran against the phase diff. **code-reviewer** found 2 confirmed
correctness bugs; **adversarial-tester** found 1 security bug + surfaced dead-code
and N+1 notes. All confirmed/BROKEN items fixed and re-verified (pytest 495, tsc 0,
lint 0). Deferred items are documented below, not silently dropped.

**FIXED:**
1. **Page-count desync (code-reviewer).** The player's render path used the new
   sections-only page formula but three helpers (`loadLesson` resume,
   `handleSectionChange`, `handleVideoEnded`) still used the old
   `sections?.length || 1`. On a **quiz-only lesson**, a student with a persisted
   `current_section` could land on a blank page with the quiz unreachable.
   Fixed with a single shared `contentPageCountFor()` helper used at all 4 sites.
2. **Two un-migrated video indicators (code-reviewer).** After 0019 blanks
   lesson-level `video_type`, `OutlineUnitCard.tsx` and `CourseDetailPage.tsx`
   still keyed their Play/FileText icon off `lesson.video_type` → always "no
   video." Switched both to `has_video` (added to `LessonListItem`).
3. **Cross-course `required_quiz` IDOR (adversarial-tester, BROKEN).** See backend
   task above — `LessonQuizScopeMixin` now scopes the quiz to the lesson's course;
   regression tests added.
4. **Dead `max_quiz_attempts` control (adversarial-tester).** Removed from the
   Details tab — the student mastery-quiz flow doesn't enforce the cap, so it
   would mislead. See frontend task note.

**DEFERRED (documented, low-risk):**
- **`has_video` N+1.** `get_has_video` adds ~1 query/lesson to list endpoints that
  already have per-row `section_count`/`question_count`/`attachment_count` method
  fields (measured ~83 queries / 20 lessons). Not new in kind; a future pass could
  `Prefetch`/annotate these endpoints. These list endpoints are unpaginated —
  worth revisiting if a course grows to hundreds of lessons.
- **Whitespace-only `video_id` → `has_video=True`.** Only reachable by bypassing
  the serializer (direct DB write); all real write paths reject it via
  `VideoFieldsValidationMixin`. Defense-in-depth only.
- **Raw-API dormant-field writes.** Documented above under Verification — keeping
  the columns was an explicit scope decision; dropping them is a future phase.

## Reminder carried out of scope (Phase 52 deploy debt)

Not part of this phase, but still open and owned by the user:
- Apply Phase 52 migrations `0017` + `0018` to Neon (snapshot first; `0018` is
  irreversible, capture per-row output). Order `0017 → 0018`.
- Post-deploy prod spot-check of a previously-broken lesson + `/api/health/?deep=1`.
- Fast-forward local `main` to `lms/main` (currently stale).
