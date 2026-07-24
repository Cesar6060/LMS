# Phase 16: Course Management UI

## Goal

Replace the modal-heavy `ManageCoursePage` with a clean, Canvas/Udemy-style
single-page course outline that instructors can navigate and edit seamlessly:
collapsible unit cards containing lesson/assignment/quiz rows with type icons,
inline "+ Add" creation, drag-and-drop reordering (@dnd-kit, keyboard
accessible), and a dedicated full-page lesson editor with live markdown
preview. Structure operations (add/rename/reorder/delete) commit immediately;
the lesson editor uses explicit Save with an unsaved-changes warning. The
phase also fills known gaps: assignment editing was never wired up, course
settings (title/description/is_active/delete) have no UI, the lesson form
never exposed Vimeo/`max_quiz_attempts`/`required_quiz`, and assignments are
matched to units by title (breaks on duplicates). All existing backend CRUD
is reused; the only backend change is extending lesson reorder to support
cross-unit moves.

## Out of scope

- Draft/published states on units or lessons (course-level `is_active`
  remains the only visibility control) — candidate for a later phase.
- WYSIWYG / TipTap rich-text editing — markdown + preview only.
- Autosave in the lesson editor (explicit Save only).
- Changes to the student-facing course player (`/learn/`), CourseDetailPage,
  gradebook, grading, or quiz-taking flows.
- Quiz question editing (outline creates the quiz shell and deep-links to the
  existing `QuizEditorPage`).
- Assignment submission/grading behavior (only the create/edit form moves).
- New notification types, analytics, or bulk import/export.

## Backend tasks

The courses/assignments/quizzes apps already expose full instructor CRUD +
reorder endpoints (see `backend/courses/views.py`, `backend/assignments/views.py`,
`backend/quizzes/views.py`). Only one behavior change:

- [x] Extend `LessonViewSet.reorder` (`PATCH /api/courses/lessons/{id}/reorder/`)
      to accept an optional `unit` id for cross-unit moves. Validate the target
      unit belongs to the **same course**; `require_course_instructor` on both
      source and target; compact `order` in the source unit and insert at the
      requested position in the target (respect `unique_together=['unit','order']`).
- [x] Tests in `backend/courses/`: cross-unit move happy path, move to a unit
      in a *different* course → 400, student/anonymous → 403 (permission-
      boundary test per `.claude/rules/backend.md`), order compaction in both
      units after the move.
- [x] No new models or migrations. (If implementation reveals a needed
      serializer tweak — e.g. exposing `unit` on lesson reads — keep it
      additive.)

## Frontend tasks

### Dependencies & services
- [x] Add `@dnd-kit/core` + `@dnd-kit/sortable` (confirm current stable
      versions; do NOT use react-beautiful-dnd — deprecated).
- [x] `services/courses.ts`: extend `reorderLesson` to pass optional target
      `unit` id. Verify `updateCourse`/`deleteCourse` signatures (already
      exist, currently unused).
- [x] `services/quizzes.ts` (or existing quiz service): ensure a
      `createQuiz(unitId, {title, description})` call exists for shell
      creation via `POST /api/quizzes/units/{unit_id}/quizzes/`.
- [x] `types/`: update shared types as needed (lesson `unit` id, quiz shell
      create payload). No `any` (`.claude/rules/frontend.md`).

### Course outline page (rebuild of `pages/instructor/ManageCoursePage.tsx`)
- [x] Header: course title, enrollment code (copy button), Settings button,
      Collapse all / Expand all. Keep existing ownership check + 403 handling.
- [x] Unit cards: drag handle (grip icon, hover-visible), chevron collapse
      (state remembered — localStorage keyed by course code), inline-editable
      title (click to edit, Enter saves, Esc cancels), item count, kebab menu
      (rename, delete with `confirm()`).
- [x] Item rows inside each unit: type icon (lesson/assignment/quiz), title,
      metadata (points, due date for assignments), hover-revealed actions
      (edit, delete via kebab). Lessons link to the lesson editor page;
      assignments open the assignment modal; quizzes deep-link to
      `QuizEditorPage`.
- [x] Inline creation: "+ Add lesson · assignment · quiz" ghost row at the
      bottom of each unit (type picker → inline title input; Enter creates,
      Esc cancels; assignment/quiz creation may open their fuller forms after
      the title step). "+ Add unit" row at page bottom.
- [x] Drag-and-drop with @dnd-kit `SortableContext`: reorder units; reorder
      lessons within a unit; move lessons across units. Optimistic update +
      PATCH on drop, rollback on failure. Keyboard sorting works (dnd-kit
      default sensors). Assignments/quizzes reorder within their unit only if
      their existing endpoints support it — otherwise render them after
      lessons and skip (do not invent new endpoints for this).
- [x] Fix the assignment→unit matching bug: match by unit **id**, not
      `unit_title` (`ManageCoursePage.tsx:402-407` in the old page).
- [x] Wire assignment **editing**: row edit action opens the existing
      assignment modal pre-filled (`editingAssignment.id` path already
      supported by the modal logic — reuse it).
- [x] Empty states (single CTA, one sentence): course with no units →
      "Create your first unit"; empty unit → "No lessons yet — add a lesson,
      assignment, or quiz."
- [x] Guided first-run flow: after `CreateCoursePage` success, land on the
      outline with the empty state focused so the add-unit → add-lesson path
      is obvious (no separate wizard).

### Course settings
- [x] Settings surface (slide-over or modal from the header button): edit
      `title`, `description`, `is_active` toggle; Danger zone with Delete
      course (typed-confirmation, then navigate to /dashboard). Uses existing
      `updateCourse`/`deleteCourse`.

### Lesson editor page
- [x] New route `/instructor/courses/:code/lessons/:lessonId/edit` wrapped in
      `InstructorRoute` (add to `App.tsx`).
- [x] Layout: title field; video settings (type: none/**youtube/vimeo**, URL →
      id extraction; add a Vimeo URL parser alongside `extractYouTubeVideoId`);
      quiz gating (`required_quiz` picker listing the course's quizzes +
      `max_quiz_attempts` number input); markdown editor with live preview
      (tabbed or split-pane, rendered with existing `react-markdown` +
      `remark-gfm` + `prose prose-neutral dark:prose-invert` classes).
- [x] Explicit Save button + dirty-state tracking; warn on navigate-away with
      unsaved changes (React Router blocker or beforeunload).
- [x] Tabs (or sections) hosting the existing managers on this page instead
      of nested modals: Sections (`SectionEditor`), Questions, Attachments
      (`AttachmentUploader`). Reuse the components; restyle only as needed to
      sit in a page instead of a modal.
- [x] Old lesson-edit modal path in the outline removed (title rename stays
      inline on the row).

### Conventions (from `.claude/rules/` + existing patterns)
- All API calls through `src/services/` — no inline axios.
- Radix `Dialog` for any remaining modals; CVA `Button` variants; `Loader2`
  spinner; inline `bg-destructive/10` error banners; native `confirm()` for
  simple deletes.
- Mind the doubled URL prefix: `/api/courses/courses/{code}/…` for
  course-scoped calls; flat `/api/courses/units/{id}/`, `/lessons/{id}/`.
- Creates go through nested parent routes only (direct viewset create raises
  PermissionDenied by design).

## Verification

- [x] `docker compose exec backend pytest` — all pass, including new
      cross-unit reorder tests (happy path, cross-course 400, student 403,
      order compaction). No pytest on host.
- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 errors (pre-existing warnings OK).
- [x] `/verify-stack` output shown as evidence.
- [x] Manual click-through as instructor (VGD101 has quizzes; use it):
  1. Create a new course → land on outline → guided empty state → add first
     unit → add first lesson inline.
  2. Outline: collapse/expand units (state survives reload), inline-rename a
     unit, drag-reorder units, drag a lesson within a unit, drag a lesson to
     a different unit — order persists after refresh.
  3. "+ Add" row: create a lesson, an assignment (full form), and a quiz
     shell → quiz row deep-links to QuizEditorPage.
  4. Edit an assignment from its row — fields pre-filled, save persists.
  5. Lesson editor page: edit markdown with live preview, set a Vimeo video,
     set required_quiz + max_quiz_attempts, Save; navigate away with unsaved
     changes → warning appears. Sections/Questions/Attachments tabs work.
  6. Course settings: edit title/description, toggle is_active, delete a
     throwaway course (typed confirmation) → redirected, course gone.
  7. As a student: verify the reordered structure renders correctly in
     CourseDetailPage and `/learn/`, and a student hitting
     `/instructor/courses/{code}/manage` still gets AccessDenied.
  8. Duplicate-title check: two units with the same title show their own
     (correct) assignments.
