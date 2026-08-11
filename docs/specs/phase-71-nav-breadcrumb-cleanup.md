# Phase 71 — Nav breadcrumb cleanup

## Goal

Move the course breadcrumb out of the header's nav row into its own slim,
full-width bar directly below the header. Today the breadcrumb is inline
markup inside `Header.tsx`, rendered as a sibling of the Dashboard/Courses
nav pills in the same flex row — with a stray chevron before the first crumb,
no truncation, no accessibility markup, and nothing at all on mobile. After
this phase, course pages show a muted, content-aligned breadcrumb bar
(`Courses ▸ ROB201 ▸ Manage`) on every screen size, the nav row holds only
the nav pills, and the breadcrumb is a proper `<nav aria-label="Breadcrumb">`
with tests guarding it.

**Decisions made in the planning interview (2026-08-09):**
- Placement: separate slim bar under the header, aligned with page content.
- Crumb label: course **code only** (URL slug uppercased, as today) — no
  data fetching or context wiring for titles.
- Mobile: the bar shows at **all breakpoints** (it becomes the only location
  cue below `md`, where nav pills are hidden).
- Extras in scope: a11y markup + unit tests. CourseToolsNav style
  unification was explicitly declined.

**Context:** phase 70 (PR #104) merged to main as `7c5d790` and deployed;
prod deep health ok. This phase renumbers the plan: content-upsert hardening
(previously penciled as phase 71) moves to **phase 72**. Five dependabot PRs
are open on `lms` (eslint/js, vite 8.2.0, jsdom 30.0.1, sentry/react
10.69.0, and a minor-and-patch group) — not part of this phase.

## Out of scope

- Course **title** in the breadcrumb (needs a header-side data source;
  revisit only if code-only proves insufficient).
- Unifying `CourseToolsNav`'s copy of the nav-pill styles with the header's.
- Any change to `BackLink` or the in-page back-link pattern.
- The mobile Sheet drawer's contents.
- Learning mode (`/courses/:code/learn`, `/map`): header stays hidden there
  and the breadcrumb bar stays hidden with it.
- All backend work — this phase is frontend-only. No migrations.

## Backend tasks

None.

## Frontend tasks

Sequential chain (all touch `Header.tsx`/`Layout.tsx` or depend on the new
component), so no `[P]` items except where noted:

- [x] Create `frontend/src/components/layout/Breadcrumbs.tsx`:
  - Move `getBreadcrumbInfo()` out of `Header.tsx` (currently lines 86–129)
    into this component; delete the unreachable
    `return parts.length > 0 ? parts : null` dead branch while moving it.
  - Prepend a root crumb **Courses → `/courses`** before the course-code
    crumb; keep the existing second-crumb labels (Manage, Gradebook, Roster,
    Quizzes, Grades, Learning, Announcements, Discussions, Edit Lesson) and
    their hrefs.
  - Render `null` when the route produces no crumbs (no empty bar) or when
    unauthenticated (same gate as today's header breadcrumb).
  - Chevrons (`ChevronRight h-4 w-4`) **between** crumbs only — no leading
    chevron.
  - Markup: `<nav aria-label="Breadcrumb">` wrapping `<ol>`/`<li>`, with
    `aria-current="page"` on the last crumb; last crumb is plain text
    (`text-foreground font-medium`), earlier crumbs are `Link`s
    (`text-muted-foreground hover:text-foreground`).
  - Truncation: `min-w-0` on the list, `truncate` + a `max-w-*` cap on each
    crumb label so long labels ellipsize instead of pushing the row.
  - Bar styling: full-width, slim (`py-2`-ish), `text-sm text-muted-foreground`,
    `border-b border-border` to read as an extension of `.header-gaming`;
    inner wrapper matches `PageContainer` alignment
    (`container mx-auto px-6 max-w-7xl`). Visible at all breakpoints — no
    `hidden md:flex`.
- [x] Wire it into `frontend/src/components/layout/Layout.tsx`: render
  `<Breadcrumbs />` immediately below `<Header />` inside the existing
  `{!isLearningMode && ...}` gate (line ~30).
- [x] Clean up `frontend/src/components/layout/Header.tsx`: remove the inline
  breadcrumb block (lines ~155–174), `getBreadcrumbInfo`, and now-unused
  imports; nav row keeps only the pills.
- [x] `[P]` Tests, `frontend/src/components/layout/Breadcrumbs.test.tsx`
  (parallel-safe once the component exists — new file, touches nothing else):
  - `/dashboard` → renders nothing.
  - `/courses/rob201` → `Courses ▸ ROB201`, code uppercased, Courses links
    to `/courses`, no leading chevron.
  - `/instructor/courses/rob201/manage` → `Courses ▸ ROB201 ▸ Manage`;
    ROB201 links to `/instructor/courses/rob201/manage`; `Manage` has
    `aria-current="page"` and is not a link.
  - One case per remaining sub-page label (Gradebook, Roster, Quizzes,
    Grades, Learning, Announcements, Discussions, Edit Lesson).
  - Unauthenticated → renders nothing.
- [x] Update this spec's checklist as items complete.

## Evidence (2026-08-09)

- Tests: `npx vitest run` → **23 files / 253 passed** (240 pre-existing +
  13 new in `Breadcrumbs.test.tsx`).
- `npx tsc --noEmit` → exit 0. `npm run lint` → 0 errors, 1 known
  `react-refresh` warning (ErrorBoundary.tsx).
- Backend: `docker compose exec -T backend pytest` → **1181 passed in
  272.55s**. `git diff --stat lms/main` touches only `frontend/` + `docs/`;
  no migrations.
- Manual click-through (local stack, Chrome automation, logged in as Emma —
  student; the manage-page *body* shows Access Denied for her, but the
  breadcrumb is route-driven so all bar checks are valid):
  1. ✅ `/instructor/courses/rob201/manage` — slim bar below header reads
     `Courses › ROB201 › Manage`; nav row has only Dashboard/Courses pills;
     no leading chevron.
  2. ✅ `Courses` crumb → course list (no bar there, as designed);
     `ROB201` crumb → `/instructor/courses/rob201/manage`.
  3. ✅ `/dashboard` — no bar, no empty strip.
  4. ⚠️ Narrow-window check: `resize_window` reported success but the
     viewport never changed (automation limitation). Structural evidence
     instead: the bar has no `hidden`/`md:` classes (old crumb was
     `hidden md:flex`), and the unit tests assert it renders — visible at
     all widths by construction. Literal narrow-window glance left to the
     user.
  5. ✅ `/courses/ROB101/map` and `/courses/ROB101/learn/255` — no app
     header, no breadcrumb bar (player landed on page 1/6, phase-70 rule
     intact).
### Review round (code-reviewer + adversarial-tester, both on the full diff)

Fixed after review:
- **`/instructor/courses/new` rendered a fabricated `NEW` course-code crumb**
  (both agents; adversarial rated it BROKEN). Now short-circuits to
  `Courses › New Course`. Verified in the browser.
- **`/instructor/courses/:code/analytics` and direct lesson view
  `/courses/:code/lessons/:id` had no leaf label**, so `aria-current`
  landed on the course code and its link back was lost. Added `Analytics`
  and `Lesson` cases.
- Test hardening: real route paths (`/quizzes/5`), 3-crumb count + root/code
  link assertions per sub-page case, first-`li`-has-no-chevron assertion,
  and a hostile-slug regression test (no markup injection, no
  `javascript:`/protocol-relative href). All XSS/href-injection attacks
  HELD — React escaping + literal href templates with `[^/]+` capture.

Deferred (pre-existing behavior, unchanged by this phase):
- `Layout.tsx`'s `isLearningMode` regex substring-matches (`/learn*`,
  `/map*`) — no current route collides; a landmine only for future routes.
- A course slug containing a keyword (e.g. `learn-basics`) yields a phantom
  sub-crumb — same `path.includes` chain as the old header.
- The bar string-matches routes without validating them, so a 404 path like
  `/manage/extra` still shows crumbs — cosmetic, page is already a 404.
- Styling notes: the bar adds `bg-background/70 backdrop-blur-sm` (reads as
  an extension of `.header-gaming`) and is intentionally not sticky.

- Pre-existing quirk noticed (not phase-71, unchanged behavior): course
  detail fetch is case-sensitive — `/courses/rob201` shows "Course not
  found" while `/courses/ROB201` loads. The breadcrumb uppercases labels
  either way; instructor crumb hrefs preserve the URL's original case,
  matching the old header behavior.

## Verification

- `cd frontend && npx tsc --noEmit` → 0 errors.
- `cd frontend && npm run lint` → 0 errors (1 known `react-refresh` warning).
- `cd frontend && npx vitest run` → all suites pass including the new
  `Breadcrumbs.test.tsx`.
- Backend untouched: `git diff --stat main` shows only `frontend/` +
  `docs/` changes; no migrations.
- `/verify-stack` PASS with output shown.
- Manual click-through (local stack):
  1. `/instructor/courses/rob201/manage` — slim bar below the header reads
     `Courses ▸ ROB201 ▸ Manage`; header nav row shows only
     Dashboard/Courses pills, no crumbs, no stray leading chevron.
  2. Click `ROB201` in the bar → lands back on the manage page root; click
     `Courses` → course list.
  3. `/dashboard` — no breadcrumb bar, no empty strip.
  4. Narrow the window below `md` — nav pills hide, breadcrumb bar remains.
  5. Open a ROB101 lesson in the player (`/learn`) — no header, no bar.
