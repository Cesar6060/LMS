# Phase 17 — Navigation Modernization

## Goal

Rebuild the app's top navigation and layout shell so the chrome feels modern and
appropriately sized. The current header is a thin 56px bar (`h-14`, `text-sm`
links) with no mobile menu, no instructor shortcuts, and a hand-rolled user
dropdown. This phase replaces it with a bold 80px header (larger Orbitron logo,
base-size nav links, bigger bell/avatar, pill/underline active state), adds a
real mobile hamburger menu, adds role-aware instructor navigation, rebuilds the
user menu and notification panel on the existing Radix `DropdownMenu` primitive,
and extracts a shared `Layout` + `PageContainer` so page chrome is consistent.
The gaming identity (neon green, Orbitron, glassy blur, starfield) stays — 
refined, not amplified: subtle glow on the active link, tidier spacing, less
visual noise.

## Out of scope

- Backend changes of any kind (no models, endpoints, or migrations).
- Redesigning page *content* (cards, dashboards, course pages) — only the
  shared chrome and page containers.
- The learning-mode player header (`CoursePlayerPage` keeps its own header;
  the global header remains hidden on `/courses/:code/learn`).
- The course-scoped `CourseSidebar` and `.sidebar-gaming` styling.
- New nav destinations beyond those listed (no search bar, no theme toggle).
- Light-theme polish beyond "nothing breaks" (app is used in dark mode).
- Promoting breadcrumbs to a second header row (bold single-bar option chosen).

## Branching note

PR #5 (phases 15+16) is open and unmerged. Cut this phase's branch from
`feat/phase-16-course-management-ui` (or from `main` after PR #5 merges) — NOT
from `lms/main` as it stands today.

## Backend tasks

- [x] None. This phase is frontend-only.

## Frontend tasks

### Header rebuild (`src/components/layout/Header.tsx`)
- [x] Bar sizing: `h-20` (80px) inner bar, `px-6` container padding
      (keep `sticky top-0 z-50` + `.header-gaming` glass blur).
- [x] Logo: `Gamepad2` icon `h-8 w-8` neon green; wordmark `text-2xl`
      using the `font-gaming` Tailwind token (remove the inline
      `fontFamily: 'Orbitron'` style); keep `text-gradient-gaming`.
      Wordmark still hidden below `sm`.
- [x] Nav links: `text-base font-medium px-4 py-2.5 rounded-lg`;
      active link gets a pill (`bg-muted`) plus a neon-green underline or
      subtle glow (`shadow-neon-green` at low opacity or a 2px accent bar);
      inactive keeps `text-muted-foreground hover:text-foreground`.
- [x] Breadcrumbs: keep the existing contextual breadcrumb logic, restyled to
      match the taller bar; still `hidden md:flex`.
- [x] Right side: bell icon `h-6 w-6`, avatar `h-9 w-9` (36px), username
      `text-base`; logged-out Login/Register buttons bumped to `size="lg"`
      or equivalent visual weight.
- [x] Desktop nav hidden below `md`; hamburger appears instead (below).

### Role-aware instructor nav
- [x] Instructors (`user.is_instructor`) get a **Teach** dropdown in the main
      nav (Radix `DropdownMenu`): "Create Course" → `/instructor/courses/new`,
      plus a "Manage" link per owned course → `/instructor/courses/:code/manage`
      (reuse the courses the header already has access to via `courseService`;
      cap the list at ~5 with a "Courses" fallback link).
- [x] Students see nav exactly as today (Dashboard, Courses); the "My Grades"
      section stays in the user dropdown.
- [x] Active-state styling on Teach when on an `/instructor/*` route.

### Radix dropdown refactor
- [x] User menu: rebuild on `components/ui/DropdownMenu` (trigger = avatar +
      name + chevron). Content: user header (name/email + Instructor badge),
      student "My Grades" course links (max 3, as today), Settings, Logout
      (destructive styling). Remove the manual `useEffect` outside-click code.
- [x] Notification panel (`src/components/notifications/NotificationBell.tsx`):
      rebuild trigger + panel on the Radix primitive, keeping current behavior:
      30s unread polling, fetch-on-open, mark-all-read, `9+` badge (badge grows
      to match the bigger bell), `w-80`+ scrollable list, unread tint.
      Item clicks must still navigate correctly (use `onSelect`/`asChild`).

### Mobile menu
- [x] Below `md`: hamburger button (`Menu` icon, `h-6 w-6`) replacing desktop
      nav links; opens a slide-in sheet/panel (Radix Dialog-based or a new
      `components/ui/Sheet.tsx` following the existing cva/cn conventions).
- [x] Sheet contents: Dashboard, Courses, instructor Teach section (if
      instructor), Settings, Logout; large touch targets (`py-3 text-base`);
      closes on navigation.
- [x] Bell and avatar remain visible in the bar on mobile.

### Shared layout shell
- [x] New `src/components/layout/Layout.tsx`: renders `<Header />`,
      `<AnimatedBackground />` (same conditional props as today), and
      `<main className="relative z-10">{children}</main>`; `App.tsx` uses it
      instead of the inline shell (learning-mode still bypasses the header).
- [x] New `src/components/layout/PageContainer.tsx`: standard
      `container mx-auto px-6 py-8 max-w-7xl` (props to override width);
      adopt it in the main top-level pages (Dashboard, Courses, Settings,
      course detail) replacing their ad-hoc `container mx-auto px-4 py-8`
      wrappers. Other pages may migrate opportunistically but are not required.
- [x] `.header-gaming` in `src/index.css`: adjust as needed for the taller bar
      (border/glow subtlety per "refine, don't amplify").

## Verification

- [x] `cd frontend && npx tsc --noEmit` — 0 errors.
- [x] `cd frontend && npm run lint` — 0 errors (pre-existing warnings OK).
- [x] Backend suite untouched but run once for the record:
      `docker compose exec backend pytest` — 227 passed (no regressions).
- [x] Run `/verify-stack` and show output.
- [x] Manual click-through (instructor@demo.com / Admin123!):
  - [x] Header is visibly taller (~80px), logo and links larger; active link
        shows pill + accent on `/dashboard` and `/courses`.
  - [x] Teach dropdown lists Create Course + owned-course Manage links; both
        navigate correctly; Teach shows active state on instructor routes.
  - [x] User dropdown (Radix): opens on click, closes on outside click and
        Escape, arrow-key navigation works; Settings and Logout work.
  - [x] Notification bell: badge count shows, panel opens, mark-all-read
        works, clicking an item navigates.
  - [x] Breadcrumbs still appear on a course page (e.g. VGD101 › Manage).
- [x] Manual click-through (student1@demo.com / Admin123!):
  - [x] No Teach menu; My Grades course links present in user dropdown.
- [x] Responsive check (devtools, ~375px width):
  - [x] Desktop links hidden, hamburger visible; sheet opens with all entries,
        closes on navigation; bell + avatar still usable.
- [x] Learning mode (`/courses/:code/learn`) still renders with NO global
      header.
- [x] Auth pages (`/login`) render correctly with the new header/logged-out
      buttons.
