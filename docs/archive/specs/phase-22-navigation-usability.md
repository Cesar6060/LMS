# Phase 22: Navigation & Button Usability

## Goal

Make every button say what it does, land where it says, and be reachable
without dead ends — for both students and instructors. Phase 17 rebuilt the
global header chrome but explicitly left page content out of scope; this
phase fixes the page-level navigation graph and button affordances that a
full audit (2026-07-18, two-agent sweep of all student and instructor
pages) found. Frontend-only; no backend, models, or endpoints change.

The audit's findings cluster into four problems:

1. **Broken or misleading destinations** — the same label goes different
   places, buttons land on the wrong role's page, breadcrumbs point away
   from where you are.
2. **Hub-and-spoke instructor tools** — Gradebook/Roster/Quizzes/Lesson
   editor interlink only through ManageCoursePage; no lateral movement.
3. **Reachability gaps** — grades absent from mobile nav entirely, key
   pages effectively URL-only, dead-end error states.
4. **Inconsistent affordances** — icon-only buttons without labels,
   hover-only controls unusable on touch, three styles of "back", native
   `confirm()` vs styled dialogs for equally destructive actions.

## Decisions made during scoping

- One vocabulary for the two student primary actions:
  **"Continue Learning"** always → `/courses/:code/learn...` (player);
  **"View Course"** always → `/courses/:code` (detail). No other labels for
  these destinations.
- Instructor course tools get a shared tab-style sub-nav
  (`CourseToolsNav`) rendered on Manage, Gradebook, Roster, and Quiz
  editor: `Overview · Gradebook · Roster · Quizzes · Student View`. This
  replaces the ghost quick-links row on Manage and the per-page
  "Back to Manage Course" text links, and kills the hub-and-spoke problem
  in one component.
- Back affordances standardize on one pattern: ghost Button with
  ChevronLeft + "Back to {destination}", where {destination} names the
  actual place it navigates to. Error states always include one.
- Quiz round trip fixes via URL param: player links to quizzes with
  `?from=learn&lesson={lessonId}`; QuizDetailPage reads it and points its
  back link AND post-submit return at the lesson instead of course detail.
  No global state needed; deep links without the param behave as today.
- Destructive confirmations standardize on the styled Dialog pattern
  StudentRosterPage already uses — extracted to a shared
  `ConfirmDialog` component. Native `confirm()`/`alert()` are removed from
  instructor pages.
- Hover-revealed controls (`opacity-0 group-hover:opacity-100`) become
  always-visible at reduced emphasis (`opacity-60 hover:opacity-100`
  + `focus-visible`) — hover-only is unusable on touch devices.
- Deliberately NOT restructuring page layouts (e.g. not moving the
  CourseDetail quizzes section into unit cards) — this phase rewires
  labels, links, and affordances, not information architecture.

## Out of scope

- Backend changes of any kind.
- Page layout/IA redesigns (section ordering, new page types, a grades
  index page).
- LessonEditor prev/next-lesson navigation and full route-blocking for
  dirty state (listed as stretch below; the existing back-button dirty
  guard stays).
- The learning-mode player's internal chrome (sidebar, footer — phase 19
  territory) beyond its Exit button label and quiz CTA.
- Light-theme work, copy rewrites beyond button/link labels.

## Tasks

### A. Shared components

- [x] `components/ui/ConfirmDialog.tsx`: extract the styled
      confirm-dialog pattern from `StudentRosterPage.tsx:481-506`
      (title, body, destructive confirm button, cancel). Roster adopts it.
- [x] `components/layout/BackLink.tsx`: ghost Button + ChevronLeft +
      "Back to {label}" — the one back-affordance used everywhere below.
- [x] `components/instructor/CourseToolsNav.tsx`: tab-style sub-nav for
      instructor course pages — Overview (`/instructor/courses/:code/manage`),
      Gradebook, Roster (`.../students`), Quizzes, Student View
      (`/courses/:code`); active tab styled like header nav pills.

### B. Global header fixes (`components/layout/Header.tsx`)

- [x] Breadcrumb course crumb on `/instructor/...` routes links to
      `/instructor/courses/:code/manage`, not the student detail page
      (bug at Header.tsx:90-93).
- [x] Fix dead branch: breadcrumb checks `/roster` but the route is
      `/students` (Header.tsx:106-107) — roster pages never get their
      crumb.
- [x] Add `/discussions` breadcrumb branch (currently absent from the
      96-110 chain).
- [x] Add `/lessons/:id/edit` breadcrumb label ("Edit Lesson").
- [x] Mobile sheet: add per-course "My Grades" links for students
      (absent entirely today, Header.tsx:304-367).
- [x] Mobile sheet Teach section: add the "All courses…" overflow link
      that desktop has (Header.tsx:177-183) — instructor courses 6+ are
      unreachable from mobile Teach today.
- [x] Desktop user dropdown: "+N more courses" overflow text
      (Header.tsx:265-269) becomes a link to `/courses`.

### C. Student flow fixes

- [x] `DashboardPage.tsx`: enrolled-course card button (360-362) relabel
      "Continue" → "View Course" (it goes to course detail); hero button
      (117-122) relabel "Continue" → "Continue Learning".
- [x] `CourseDetailPage.tsx`: "Learning Mode" button (328-333) relabel →
      "Continue Learning".
- [x] `CoursesPage.tsx`: student course cards get a "View Course" button
      so cards aren't CTA-less (138-167).
- [x] Quiz round trip:
  - [x] `CoursePlayerPage.tsx:636-641`: required-quiz CTA becomes a real
        primary Button ("Take Quiz") linking with
        `?from=learn&lesson={lessonId}`; keep the amber notice styling
        around it.
  - [x] `QuizDetailPage.tsx`: when `from=learn`, back links (124-130,
        229-235) become "Back to Lesson" →
        `/courses/:code/learn/{lessonId}`, and the results state gets a
        primary "Back to Lesson" button alongside Retake.
  - [x] `QuizDetailPage.tsx` error state (107-117): add BackLink (dead
        end today).
  - [x] In-quiz state: add an exit affordance in the sticky header
        (342-347) — "Exit Quiz" opening ConfirmDialog ("answers will be
        discarded"); the bottom "Cancel" (385-391) uses the same dialog.
  - [x] Retake button style consistent between intro (306, primary) and
        results (177-181, outline) — primary in both.
- [x] `MyGradesPage.tsx`: quiz rows (231-267) link to
      `/courses/:code/quizzes/{id}` so a student can click through to
      retake.
- [x] `CoursePlayerPage.tsx:550-558`: "Exit" relabel → "Back to Course";
      keep icon-only on mobile but add `aria-label`/`title`.
- [x] List rows become full-card click targets (match CourseDetail's
      row-link pattern): `DiscussionsPage.tsx:186-191`,
      `AnnouncementsPage.tsx:255-260`.
- [x] `AnnouncementDetailPage.tsx:146-152`: back link goes to the course
      (`/courses/:code`) when the student arrived from CourseDetail —
      mirror the quiz `?from=` approach with `?from=course`; default stays
      "Back to Announcements".

### D. Instructor flow fixes

- [x] Adopt `CourseToolsNav` on `ManageCoursePage` (replacing the ghost
      quick-links row at 523-552), `GradebookPage` (replacing back link at
      159-165), `StudentRosterPage` (253-259), `QuizEditorPage` (338-344).
- [x] `DashboardPage.tsx:324-343`: instructor card "Manage" button
      navigates to `/instructor/courses/:code/manage` directly (today it's
      decorative inside a Link to student detail — 2 hops to manage).
      Card link itself stays on course detail; make the button a real
      stopPropagation link.
- [x] `CreateCoursePage.tsx`: drop the duplicate "Back to Courses"
      (47-52); single Cancel → `/dashboard` (its actual entry points are
      Dashboard and the Teach menu, not `/courses`).
- [x] `LessonEditorPage.tsx:193-196`: back button label "Course Outline" →
      BackLink "Back to Manage Course" (same destination, standard
      wording); not-found state (179-182) label matches.
- [x] `QuizEditorPage.tsx` error state (316-326): add BackLink (true dead
      end today).
- [x] `GradebookPage.tsx` error state (146-148): destination →
      manage page, not student course detail.
- [x] `ManageCoursePage.tsx` error state (450-452): destination →
      `/dashboard` ("Back to Dashboard") — `/courses` is the student list.
- [x] Replace native `confirm()`/`alert()` with ConfirmDialog:
      `ManageCoursePage.tsx:220,257,277` (unit/lesson/quiz deletes — unit
      delete copy must say it cascades lessons+quizzes),
      `QuizEditorPage.tsx:168,254` (quiz/question deletes; validation
      alerts at 218,225 become inline error text or toast).
- [x] `OutlineUnitCard.tsx`: hover-revealed drag handles and row actions
      (205, 238, 319, 420) become always-visible at reduced opacity.
- [x] `QuizEditorPage.tsx:370-373`: quiz-row expand becomes a real button
      with a chevron expand indicator; "Edit" (381-390) relabel →
      "Edit Details" (it edits metadata, not questions).

### E. Icon-button labeling sweep

Every icon-only button gets `aria-label` + `title`:

- [x] `ThreadDetailPage.tsx`: thread Edit/Delete (271-284), reply
      Edit/Delete (313-327).
- [x] `AnnouncementsPage.tsx`: row Edit/Delete (284-298).
- [x] `StudentRosterPage.tsx`: remove-student (402-410).
- [x] `QuizEditorPage.tsx`: quiz delete (391-401), question delete
      (451-458), choice delete (600-610).
- [x] `StudentRosterPage.tsx:344-373`: sortable `th onClick` headers become
      buttons (keyboard access).

### Stretch (only if the above lands clean)

- [ ] LessonEditor: prev/next-lesson buttons within the unit.
- [ ] LessonEditor: tab state (Content/Sections/Questions/Attachments) in
      the URL query.
- [ ] CourseDetail: instructor sees per-lesson "Edit" affordance on lesson
      rows instead of being sent to the student player.

## Verification

- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 new errors.
- [x] Backend untouched; run once for the record:
      `docker compose exec backend pytest` — 192 passed.
- [x] `/verify-stack` output shown.
- [ ] Manual click-through (student1@demo.com): dashboard hero says
      "Continue Learning" and opens the player; card says "View Course";
      lesson → required quiz → back lands on the lesson; quiz error/cancel
      paths all have exits; My Grades rows click through to quizzes;
      mobile sheet shows grades links; discussions/announcements cards are
      fully clickable.
- [ ] Manual click-through (instructor@demo.com): dashboard card "Manage"
      opens manage directly; tools tabs move laterally
      Manage↔Gradebook↔Roster↔Quizzes; breadcrumb course crumb stays in
      instructor-land; roster crumb appears; all deletes confirm via
      styled dialog; outline row actions visible without hover.
- [ ] Mobile spot-check (~375px): sheet nav includes grades (student) and
      Teach overflow (instructor); outline actions tappable.

## Implementation addendum (2026-07-19)

Shipped in PR #10 (`feat/phase-22-navigation-usability`). Deviations and
additions beyond the spec text, driven by live screenshot feedback during
implementation:

- **CourseToolsNav placement**: rendered at the very top of all four
  instructor tool pages (above the page title), not inside the header
  block — it reads as a sub-nav under the global header. Tab text is
  `text-base` to match the header nav pills exactly.
- **Replacing the Manage quick-links row dropped its Announcements
  link** (the tab set is Overview · Gradebook · Roster · Quizzes ·
  Student View per the scoping decision). Announcements remain reachable
  via Student View → course detail. Revisit if that hop annoys.
- **Readability pass** (user feedback: fonts too small, margins too big):
  Manage and Quiz editor widened `max-w-4xl` → `max-w-6xl`; outline rows
  use `text-base` titles with `text-sm` metadata.
- **Enrollment code panel**: the Manage header's enrollment code was
  promoted from an inline meta line to a highlighted neon-bordered panel
  (large mono code + labeled copy button) — important shareable info
  must be prominent.
- **Add affordances are real buttons**: the outline's "Add lesson ·
  quiz" inline text links became "Add Lesson" / "Add Quiz" outline
  Buttons; the "Add unit" dashed row was enlarged to match.
- **No single-action overflow menus**: quiz rows' ⋮ menu held only
  Delete, so it became a visible trash button. Lesson/unit ⋮ menus stay
  (they hold Rename + Delete). Row action buttons grew to h-8 with
  aria-labels; row meta text is `text-base`.
- **Dashboard instructor "Manage" button** navigates via
  `preventDefault` + `stopPropagation` + `useNavigate` rather than a
  nested `<Link>` (nested anchors are invalid HTML).
- **MyGrades / Announcements rows** use row-`onClick` navigation with a
  real `<Link>` on the title (`stopPropagation`) since rows contain
  other interactive controls; Discussions rows wrap the whole card in a
  `<Link>` (no inner controls).
