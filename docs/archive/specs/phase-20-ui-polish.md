# Phase 20: UI Typography Raise & Visual Polish

## Goal

Raise the app's base font sizes globally and make the UI consistent, balanced,
and modern. Today the app mixes two scales: the recently modernized Header
(phase 17) and learning mode (phase 19) use `text-base`+ with roomy padding,
while the bulk of older pages remain compact `text-sm` (258 uses). The raise
happens once, centrally, by remapping Tailwind's `fontSize` scale; the rest of
the phase normalizes the inconsistencies that remapping can't fix — split page
heading sizes, ad-hoc containers/padding, disagreeing title components — and
refines (not removes) the neon/gaming identity so modern leads and gaming
accents. Dark-only stays.

## Out of scope

- Light mode / theme toggle (ThemeContext stays a forced-dark no-op)
- Any backend change (this phase is 100% frontend; test count stays 192)
- Mobile/responsive overhaul (fix nothing that isn't broken by our changes)
- New features (Instructor Analytics Dashboard remains the next feature phase)
- Learning mode layout (CoursePlayerPage/CourseSidebar geometry was just done
  in phase 19 — only the `text-[15px]` cleanup below touches it)
- Removing the gaming identity (Orbitron/neon stay, refined)

## Backend tasks

None. Do not touch `backend/`.

## Frontend tasks

### 1. Global font scale (the raise)

- [x] Remap `fontSize` in `tailwind.config.mjs` with matching line-heights:
      `xs` 12→13px (`0.8125rem`/`1.125rem`), `sm` 14→15px
      (`0.9375rem`/`1.375rem`), `base` 16→17px (`1.0625rem`/`1.625rem`),
      `lg` 18→19px (`1.1875rem`/`1.75rem`). `xl` and up unchanged.
- [x] Replace the bespoke `text-[15px]` in `CourseSidebar.tsx:204` with
      `text-sm` (identical 15px after the remap — zero visual change).
- [x] Sweep for other arbitrary `text-[...px]` values; migrate to scale steps.
      (Two `text-[10px]` in WeekCalendar → `text-xs`; chips truncate so the
      13px bump is safe.)
- [x] Sanity-check fixed-height components (`Button` h-9/h-10/h-11, `Input`
      h-10, `TabsList` h-10) for clipping at the new sizes; bump heights only
      where text actually clips. (≥7px slack everywhere; no bumps needed.)

### 2. Unify headings & titles

- [x] Standard: page H1 = `text-3xl font-bold`; page-section headers =
      `text-xl font-semibold`; card/dialog/sheet titles = `text-xl`.
- [x] Raise `text-2xl` H1s to `text-3xl`: MyGradesPage, StudentRosterPage,
      GradebookPage, QuizEditorPage, QuizDetailPage, DiscussionsPage,
      ThreadDetailPage, AnnouncementsPage, AnnouncementDetailPage.
- [x] Raise LessonEditorPage H1 (`text-xl`) to `text-3xl`.
      **Deviation:** raised to `text-2xl font-bold` instead — the title sits
      inline in a breadcrumb toolbar row next to a small ghost button and the
      Save button; `text-3xl` breaks that row's balance.
- [x] `CardTitle` (`ui/Card.tsx:33`) `text-2xl` → `text-xl`; visually check
      dashboard/stat cards still read right (stat *numbers* keep `text-2xl` —
      they are separate divs, unaffected).
- [x] `DialogTitle` (`ui/Dialog.tsx:88`) and `SheetTitle` (`ui/Sheet.tsx:91`)
      `text-lg` → `text-xl`.

### 3. Standardize page containers

- [x] Every page renders through `PageContainer` (consistent `px-6 py-8`);
      migrated all 34 raw-container instances across 12 page files.
- [x] Deliberate max-width tiers via the `maxWidth` prop: narrow forms
      `max-w-2xl` (CreateCourse), standard forms/editors `max-w-4xl`
      (Settings, QuizEditor, QuizDetail, ManageCourse), reading `max-w-3xl`
      (AnnouncementDetail, ThreadDetail), content lists `max-w-6xl`
      (Dashboard, MyGrades, LessonEditor, Announcements, Discussions),
      wide data default `max-w-7xl` (Courses, CourseDetail, Gradebook,
      Roster).
- [x] Learning mode (`/courses/:code/learn`) is exempt — untouched.

### 4. Component polish (`src/components/ui/`)

- [x] One coherent pass on Button/Input/Tabs/DropdownMenu: controls were
      already consistent (`text-sm` sizing, focus rings, transitions) and now
      inherit the raised 15px scale; Button `neon` variant tokenized
      (`bg-[#22c55e]` → `bg-primary` + hover state).
- [x] Card pass: spacing already consistent (`p-6`); hover elevation made
      opt-in via `card-interactive` (blanket `.dark .card-gaming:hover` glow
      removed); clickable cards (Courses grid, Dashboard cards) opted in with
      an explicit hover border for dark mode.
- [x] `DropdownMenuLabel` `text-xs` → judgment call: **kept `text-xs`** — it
      is a muted menu section label, conventional at the small size (now
      13px).

### 5. Refine gaming identity (`src/index.css`, `tailwind.config.mjs`)

- [x] Orbitron (`font-gaming`) restricted to the logo and level badges —
      already true except two inline `fontFamily: 'Orbitron'` eyebrow labels
      on DashboardPage; replaced with tokenized uppercase-tracked eyebrows.
- [x] Reduce glow intensity: softened `.btn-neon` hover, `.text-neon`,
      progress/XP bars, `.level-badge`, `.hover-glow`, the `boxShadow`
      neon presets, and the `pulse-glow` keyframes (full-opacity glows →
      ~half-alpha, smaller radii).
- [x] Audit accent-color usage: hardcoded `#22c55e` → `primary` token and
      `#06b6d4` → `accent` token across WeekCalendar, AddReminderModal,
      MakeAnnouncementModal, DashboardPage, Login/RegisterPage. Kept
      deliberately: AnimatedBackground ambient particles (decorative system)
      and the Dashboard purple/pink second-metric gradient (distinct status).
- [x] Grid background and scanline utilities kept; both are ≤3% alpha and do
      not fight readability.

### 6. Loading & empty states

- [x] List pages get `Skeleton`-based loading layouts matching the loaded
      shape. (Courses, Announcements, Discussions, Roster, Gradebook already
      had them; MyGrades and QuizDetail were spinner-only — replaced.)
- [x] Empty states get icon + one-line message + CTA where an action exists:
      Discussions (New Thread), Announcements (New Announcement, owner only),
      Roster (Invite Student), Gradebook (Go to Roster / Create Quiz),
      MyGrades (icon + message, no CTA — students can't add quizzes).
- [x] Instructor vs student CTAs respect role (owner-gated announcement CTA;
      student-only enroll CTA on Courses was already role-aware).

## Verification

- [x] `docker compose exec backend pytest` — **192 passed** (backend
      untouched).
- [x] `cd frontend && npx tsc --noEmit` — **0 errors**.
- [x] `cd frontend && npm run lint` — **0 errors** (24 pre-existing
      `react-hooks/exhaustive-deps` warnings).
- [x] `grep -rn "text-\[1" frontend/src` returns nothing (no arbitrary px
      font sizes left).
- [x] `grep -rln "container mx-auto" frontend/src/pages` returns nothing
      (all pages on PageContainer; the class lives only inside
      PageContainer itself).
- [x] Manual click-through (dark mode, desktop): Dashboard → Courses →
      CourseDetail → learning mode (confirm phase-19 layout untouched) →
      Announcements list+detail → Discussions list+thread → MyGrades →
      Settings; as instructor: ManageCourse → Gradebook → Roster →
      QuizEditor. Check: headings consistent, no clipped buttons/inputs,
      loading skeletons appear, empty states render, glows subtler.

## Notes

- Cut the branch from `main` **after PR #8 (phase 19) merges** — done
  (`feat/phase-20-ui-polish` cut from the PR #8 merge commit).
- The font remap silently changes `prose` (typography plugin) surroundings —
  ReactMarkdown lesson content uses `prose` defaults; verify lesson body text
  still harmonizes with the raised UI scale in the click-through.
