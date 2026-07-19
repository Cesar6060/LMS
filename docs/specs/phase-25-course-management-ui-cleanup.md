# Phase 25 — Course Management margin consistency + remove "Teach" navbar dropdown

## Goal
Two small, frontend-only UI cleanups. First, make the instructor Course Management
tabs visually consistent: the **Overview** and **Quizzes** tabs currently cap their
content at `max-w-6xl` while **Gradebook** and **Roster** use `max-w-7xl`, so on wide
viewports Overview/Quizzes look more inset (wider horizontal margins). Standardize
Overview and Quizzes on `max-w-7xl` so all four Course Management tabs share identical
horizontal margins. Second, remove the top-navbar **"Teach"** dropdown entirely (both
desktop and mobile), including its now-unused supporting state/effect/constants/icons,
leaving no replacement in its place. No instructor navigation is stranded by the
removal — every destination remains reachable from the Dashboard, Courses page, course
cards, CourseDetail, and `CourseToolsNav`.

## Out of scope
- Any backend change (models, migrations, endpoints, serializers). This is frontend-only.
- Changing the shared `PageContainer` component's defaults or its `px-6`/`py-8`/`mx-auto`
  values — only the per-page `maxWidth` prop on Overview and Quizzes changes.
- Touching Gradebook or Roster layout (they are the reference; leave them as-is).
- Adding any replacement navbar link/menu for the removed "Teach" dropdown.
- Vertical spacing, card styling, or any other visual change beyond horizontal max-width.
- The `DropdownMenu` UI primitive itself (still used by the account/user menu — keep it).
- The benign instructor `403` and unit-quiz progress items deferred from Phase 24.

## Backend tasks
None.

## Frontend tasks

### Margin consistency (Overview + Quizzes → `max-w-7xl`)
- [x] `frontend/src/pages/instructor/ManageCoursePage.tsx`: changed to `<PageContainer>`
      (default width, matches Gradebook/Roster). Both the main render and the error state
      `PageContainer` were updated for consistency.
- [x] `frontend/src/pages/instructor/QuizEditorPage.tsx`: changed the main render **and** the
      loading/error states to `<PageContainer>` (default), so the width doesn't jump between
      loading and loaded.
- [x] Grepped both files afterward: no remaining `max-w-6xl`.

### Remove the "Teach" dropdown (all in `frontend/src/components/layout/Header.tsx`)
- [x] Deleted the desktop "Teach" dropdown block.
- [x] Deleted the mobile Sheet "Teach" section.
- [x] Deleted the now-unused supporting code:
      - `taughtCourses` / `setTaughtCourses` state and the `getInstructorCourses()` effect.
      - `MAX_TEACH_COURSES` constant.
      - `isTeachActive` and `teachOverflow`.
- [x] Pruned imports: removed icons `GraduationCap`, `PlusCircle`, `ClipboardList` and the
      `InstructorCourse` type import. Kept `ChevronDown`, `BarChart3`, the `DropdownMenu*`
      primitives, and `courseService` (still used by the account menu / student enrollments).
- [x] Account/user dropdown and other navbar links (Courses, Dashboard) untouched — only the
      Teach entry removed, nothing replaces it. (tsc passes, confirming no dangling refs.)

## Verification
- [x] `cd frontend && npx tsc --noEmit` → 0 errors.
- [x] `cd frontend && npm run lint` → 0 errors, 23 warnings (Phase 24 baseline, not exceeded;
      no new unused-var/import warnings introduced).
- [x] `cd backend && docker compose exec -T backend pytest` → 196 passed (no backend change).
- [~] Manual click-through as **instructor** (`instructor@demo.com` / `Admin123!`)
      — **user-confirmed visually** (Phase 26): browser automation was unavailable in
      the agent environment, so the DOM/visual pass was handed to the user. Agent-side
      verification done in Phase 26: stack healthy (`docker compose ps` all up, frontend
      HTTP 200, backend serving), instructor login works via API (HTTP 200), and code-level
      sanity confirmed (`grep "Teach"` in `Header.tsx` empty; `grep "max-w-6xl"` in
      `ManageCoursePage.tsx`/`QuizEditorPage.tsx` empty). Checks the user confirms:
      1. Top navbar shows **no "Teach" item** on desktop and none in the mobile menu.
      2. Account/user dropdown still opens and works; Courses/Dashboard links still work.
      3. Instructor can still reach **Create Course** from the Dashboard ("New Course") and
         Courses page, and **Manage** from a Dashboard course card / CourseDetail.
      4. Open a course's Course Management: **Overview**, **Quizzes**, **Gradebook**,
         **Roster** tabs all have identical left/right margins at a wide (>1280px) viewport
         — Overview and Quizzes no longer look more inset than Gradebook/Roster.
      5. Quizzes tab: width does not visibly jump between the loading state and loaded state.
- [~] 0 new console errors during the click-through — user to confirm during the visual pass.

## Reference (from investigation)
- Shared shell: `frontend/src/components/layout/PageContainer.tsx:11` —
  `cn('container mx-auto px-6 py-8', maxWidth, className)`, default `maxWidth='max-w-7xl'`.
  Only the `maxWidth` prop differs between tabs; `px-6`/`mx-auto` are identical.
- Tab → component: Overview=`ManageCoursePage`, Quizzes=`QuizEditorPage`,
  Gradebook=`GradebookPage`, Roster=`StudentRosterPage`; all render `PageContainer` +
  `CourseToolsNav` (`frontend/src/components/instructor/CourseToolsNav.tsx`).
- "Teach" dropdown is only in `Header.tsx`; no destination is stranded by removal
  (Create Course, Manage, and `/courses` are all reachable from other entry points).
