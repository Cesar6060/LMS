# Phase 24: Curriculum Editor UI Polish

## Goal

Polish the instructor curriculum editor (the unit → lesson/quiz outline on
`ManageCoursePage`) so it reads as a clear, nested hierarchy with obvious,
non-cryptic controls. Today every lesson and the unit header hide their
destructive action behind a three-dots (`⋮`) overflow menu, lesson/quiz rows
are flat hover-tinted list items with no visual containment, the Add
Lesson/Add Quiz buttons are small and easy to miss, and nothing on screen
tells an instructor that "Add Quiz" creates a **unit-wide** quiz distinct from
the per-section comprehension quizzes added inside the lesson editor. This
phase fixes all four. **Frontend-only**: no models, migrations, endpoints, or
serializers change — the entire diff lives in
`frontend/src/components/manage/OutlineUnitCard.tsx`.

## Context (confirmed during scoping)

- The editor is rendered entirely by
  `frontend/src/components/manage/OutlineUnitCard.tsx`; the parent page
  `frontend/src/pages/instructor/ManageCoursePage.tsx` maps units into it and
  owns all handlers (`onRenameLesson`, `onDeleteLesson`, `onAddQuiz`, etc.).
- Lesson rows are rendered by `SortableLessonRow` (dnd-kit draggable). The `⋮`
  menu (lines ~253–266) holds exactly **Rename** (inline) + **Delete**. The
  pencil button (lines ~230–240) links to the full lesson editor.
- The unit header has its own identical `⋮` menu (Rename + Delete); the unit
  title is **already** click-to-rename via `InlineTitle`.
- Quiz rows are inline JSX (not a component, not draggable) and **already** use
  a bare red trash icon — the pattern lessons will now match.
- Two separate quiz systems exist and must NOT be conflated:
  - **Unit quiz** = `quizzes.Quiz` (FK → `Unit`), created by "Add Quiz" here,
    graded, sibling of lessons. This is what this editor shows.
  - **Section comprehension quiz** = `courses.LessonQuestion` (FK → `Lesson`),
    added inside the lesson editor, gates lesson completion. Never appears as a
    row in this outline.
  This phase adds a "Unit Quiz" label so instructors can tell them apart. No
  data-model change — labeling is display text only.

## Out of scope

- Any backend change (models, migrations, endpoints, serializers, permissions).
- The lesson editor, the section editor (`SectionEditor.tsx`), and the
  comprehension-quiz UI — untouched.
- The authoring-efficiency / bulk-import work (split-on-delimiter) deferred
  from phase 23 — that is a separate future phase, not folded in here.
- Drag-and-drop behavior, collapse/expand, and the reorder logic — no
  functional change; only the row's visual container and action controls change.
- Adding real "duplicate" or "move to unit" actions — the `⋮` menu had none, so
  removing it loses no functionality beyond relocating Rename.

## Decisions made during scoping

1. **`⋮` → trash everywhere, Rename moves to the title.** Both lesson rows and
   the unit header drop the `DropdownMenu` entirely and expose a direct red
   trash icon button (matching the existing quiz-row pattern). To preserve
   inline rename, the **lesson title becomes click-to-rename** via the existing
   `InlineTitle` component (the unit title already works this way). The pencil
   button remains the "open full editor" affordance.
2. **Bordered sub-cards for nesting.** Each lesson and quiz row becomes its own
   bordered, rounded, padded container with vertical gap between rows
   (`space-y-2`), visually nested inside the unit `Card`. Use a light border
   (`border border-border rounded-lg`), NOT the full `card-gaming` neon-glow
   treatment, to keep the parent/child hierarchy legible.
3. **Full-width dashed add-bar.** Replace the two small `outline`/`sm` buttons
   with a more prominent add affordance at the bottom of each unit: a
   full-width dashed-border container holding "+ Add Lesson" and "+ Add Quiz"
   at default (not `sm`) size, reading clearly as the unit's call-to-action.
4. **"Unit Quiz" label.** Quiz rows show a small "Unit Quiz" badge next to the
   title, and the add button reads "+ Add Unit Quiz", to distinguish from the
   per-section comprehension quizzes. Display text only.

## Frontend tasks

All in `frontend/src/components/manage/OutlineUnitCard.tsx` unless noted.

### Lesson rows (`SortableLessonRow`)
- [x] Remove the `DropdownMenu`/`DropdownMenuTrigger`/`DropdownMenuContent`/
  `DropdownMenuItem`/`DropdownMenuSeparator` usage and the `MoreVertical`
  import from lesson rows.
- [x] Replace the `⋮` trigger with a direct trash icon button reusing the
  quiz-row pattern: `variant="ghost" size="sm" className="h-8 w-8 p-0
  text-destructive hover:text-destructive"`, `aria-label={`Delete lesson
  ${lesson.title}`}`, `title="Delete lesson"`, `onClick={() =>
  onDelete(lesson.id)}`. Keep the pencil edit link as-is (opens the editor).
- [x] Make the lesson title click-to-rename: render `InlineTitle` (value =
  `lesson.title`, `onSave` → `onRename(lesson.id, title)`) in the non-editing
  state instead of the plain `<Link>`. Keep the pencil as the path to the full
  editor. Preserve the existing `editing` state machine.
- [x] Wrap each row `<li>` as a bordered sub-card: `border border-border
  rounded-lg px-3 py-2.5` (replacing the flat `rounded-md px-2 py-2
  hover:bg-muted/50`), keeping the drag handle, icon, title, and action
  cluster layout. Retain `isDragging` opacity and the `group` hover reveal of
  the action cluster.

### Quiz rows
- [x] Wrap quiz `<li>` in the same bordered sub-card treatment as lesson rows.
- [x] Add a small "Unit Quiz" label next to the quiz title. No `Badge`
  primitive exists in `components/ui/`, so use a `<span>` with muted, small,
  bordered/rounded styling (e.g. `text-xs text-muted-foreground border
  border-border rounded px-1.5 py-0.5`). Keep the existing pencil + red trash
  buttons.

### Unit header
- [x] Remove the header's `⋮` `DropdownMenu` (Rename + Delete). Replace with a
  direct trash icon button (`onClick={() => onDeleteUnit(unit.id)}`,
  `aria-label={`Delete unit ${unit.title}`}`). The unit title is already
  click-to-rename via `InlineTitle`, so Rename needs no other home.

### Add-bar (`InlineAddRow`)
- [x] Replace the two `variant="outline" size="sm"` buttons with a prominent
  full-width dashed-border add-bar (e.g. a `div` with `border border-dashed
  border-border rounded-lg` wrapping the two buttons at default size). Keep the
  existing inline-input `mode` behavior (click → input, Enter to create, Esc to
  cancel) unchanged.
- [x] Reword the quiz button to "Add Unit Quiz" (the lesson button stays "Add
  Lesson"). Update the inline input placeholder accordingly if it echoes the
  mode name.

### Housekeeping
- [x] Remove now-unused imports (`MoreVertical`, the `DropdownMenu*` cluster)
  from the file once both menus are gone.
- [x] Confirm the `group`/`opacity` hover-reveal still works for the new
  bordered rows, and that action buttons remain reachable (they should stay
  visible enough to be usable on touch, per the app's affordance conventions).

### Verify no regressions in the parent
- [x] `ManageCoursePage.tsx` passes the same props (`onDeleteLesson`,
  `onRenameLesson`, `onDeleteUnit`, `onDeleteQuiz`, `onAddLesson`,
  `onAddQuiz`) — no prop signature changes should be needed. Confirm nothing in
  the page references the removed dropdown.

## Verification

Frontend-only phase; no backend/pytest changes expected.

- [x] `cd frontend && npx tsc --noEmit` → **0 errors**.
- [x] `cd frontend && npm run lint` → no **new** errors (pre-existing warnings
  may remain; do not introduce new ones, especially unused-import from the
  removed dropdown).
- [x] `cd backend && pytest` → still green (should be unaffected; run to prove
  it).
- [x] Run `/verify-stack` and paste the output as evidence before marking the
  phase complete.
- [x] **Manual click-through** at `localhost:5173`, logged in as an instructor,
  on a course's Manage page (verified via headless-Chrome driver against
  `VGD101` — screenshots + interaction assertions, 0 console errors):
  1. Each lesson and quiz renders inside its own bordered sub-card with clear
     spacing between rows, nested inside the unit card.
  2. No `⋮` menu appears anywhere — lesson rows, quiz rows, and the unit
     header each show a direct red trash icon.
  3. Clicking a lesson **title** enters inline rename; Enter saves, Esc
     cancels; the pencil still opens the full lesson editor.
  4. The lesson trash icon deletes the lesson (through the existing confirm
     dialog); the unit trash icon deletes the unit; the quiz trash icon deletes
     the quiz — all still work.
  5. Quiz rows show a "Unit Quiz" label; the add-bar shows a prominent
     full-width dashed control with "+ Add Lesson" and "+ Add Unit Quiz".
  6. "+ Add Lesson" and "+ Add Unit Quiz" still open the inline input and
     create the item on Enter; the new item appears as a bordered sub-card.
  7. Drag-to-reorder lessons and collapse/expand still work unchanged.

## Added during implementation (beyond original scope)

**Secure unit deletion (type-to-confirm).** Because deleting a unit cascades
to every lesson and quiz inside it, the unit delete now requires more friction
than a lesson/quiz delete. The shared `ConfirmDialog` gained an optional
`confirmDisabled` prop; on `ManageCoursePage`, the unit-delete dialog shows a
cascade warning and an input that must match the unit's name (trimmed,
case-insensitive) before the destructive **Delete Unit** button enables.
Lesson and quiz deletes are unchanged (single-click confirm). Files touched:
`frontend/src/components/ui/ConfirmDialog.tsx`,
`frontend/src/pages/instructor/ManageCoursePage.tsx`. Verified via the driver:
confirm button is disabled on open, stays disabled for a wrong name, and
enables only on the exact unit name.

**Unit quizzes now visible in learning mode.** Previously unit quizzes
(`quizzes.Quiz`) appeared only on the course landing page, never in the
`CoursePlayerPage` learning experience. `CoursePlayerPage` now fetches
`quizzesService.getCourseQuizzes(code)` alongside the course and passes them to
`CourseSidebar`, which renders each unit quiz as a row under its unit's lessons
(amber quiz icon, "Unit Quiz · N pts" label, green check when the student has
passed). Clicking a quiz navigates to the existing `QuizDetailPage` with
`?from=learn`, and that page's back-link/return-button logic was extended so a
learn-originated unit quiz returns to learning mode (`/courses/:code/learn`)
rather than the landing page. Files touched:
`frontend/src/pages/courses/CoursePlayerPage.tsx`,
`frontend/src/components/course/CourseSidebar.tsx`,
`frontend/src/pages/quizzes/QuizDetailPage.tsx`. Verified via the driver as both
instructor and enrolled student: the quiz row renders in the sidebar and the
round-trip to the quiz and back works with 0 console errors.

**"Student View" opens learning mode.** The instructor `CourseToolsNav`
"Student View" tab pointed at the course landing page (`/courses/:code`), which
is not what a student actually experiences. It now points at learning mode
(`/courses/:code/learn`) so instructors preview the real player. File touched:
`frontend/src/components/instructor/CourseToolsNav.tsx`. Verified via the driver:
clicking "Student View" lands on `/courses/VGD101/learn/:lessonId` with the
learning-mode chrome.
