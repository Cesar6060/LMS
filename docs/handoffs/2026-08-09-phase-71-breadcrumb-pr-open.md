# Handoff: Phase 71 — breadcrumb bar, PR open, not merged

## Current state
**Phase 71 is code-complete, reviewed, verified. PR #105 is open and NOT
merged.** https://github.com/Cesar6060/LMS/pull/105 — branch
`phase-71-nav-breadcrumb-cleanup`, commits `dd66a53` (feature) + `43655ab`
(review fixes). Earlier today the user merged phase 70 (PR #104 →
`7c5d790`); prod deep health verified ok.

Created: `frontend/src/components/layout/Breadcrumbs.tsx` (+ `.test.tsx`,
17 tests). Modified: `Header.tsx` (inline breadcrumb removed),
`Layout.tsx` (bar renders under Header inside the learning-mode gate),
spec `docs/specs/phase-71-nav-breadcrumb-cleanup.md` (all items checked,
Evidence + review round recorded).

Verify (post-fix re-run): pytest **1181 passed** (4m32s), tsc **0**, lint
**0 errors** (known react-refresh warning), vitest **24 files / 257
passed**. No migrations; diff touches only `frontend/` + `docs/`.
Browser click-through done as Emma (student) — breadcrumb is route-driven
so the instructor manage-page body being Access Denied didn't matter.

## In progress / not done
1. **PR #105 not merged.** Merging rebuilds the frontend (Cloudflare
   Pages); backend deploy is a no-op (no backend changes). No env vars.
2. Narrow-window (<md) look was verified structurally (no `hidden`/`md:`
   classes), not by an actual resize — Chrome automation resize_window
   reported success but the viewport never changed. One manual glance.

## Next steps
1. Review and merge PR #105; verify by loading any course page in prod and
   checking the bar (`Courses › <code> › <page>`).
2. **Phase 72 is content-upsert hardening**: the three `_content_upsert`
   findings (phase 69) + page-scoped `video_position` (phase 70 deferral).
3. Five dependabot PRs open on `lms` (eslint/js 10.0.1, vite 8.2.0, jsdom
   30.0.1, sentry/react 10.69.0, minor-and-patch group) — remember
   `migrate --check` after any dependency bump.
4. Carried owner actions (phases 69/70, untouched): Neon `production`
   `protected: false`; `THROTTLE_JOIN_CODE`/`THROTTLE_INVITE_LINK` unset in
   Render; `_dmarc` + root SPF absent; invite-deliverability test; JAVA101
   answer rotation.

## Decisions made
- Own bar under the header (not restyled-inline, not removed); course
  **code only** — no title fetch in the header; bar visible at all
  breakpoints; a11y markup + tests in scope, CourseToolsNav unification
  declined. All from the planning interview.
- `/instructor/courses/new` short-circuits to `Courses › New Course` — the
  unanchored course regex otherwise fabricates a `NEW` course code (the
  adversarial pass's one BROKEN).
- Deferred as pre-existing: `isLearningMode` substring regex, phantom
  sub-crumb on keyword-bearing slugs, crumbs on 404 paths, case-sensitive
  course-detail fetch (`/courses/rob201` 404s; `/courses/ROB201` loads).

## Gotchas discovered
- `resize_window` in Chrome automation silently fails to change the
  viewport (reports success, screenshots stay full-size).
- Shell cwd persists between Bash calls — a `git add frontend/...` from
  inside `frontend/` fails with pathspec errors; cd to repo root first.

## Files to read first
1. `docs/specs/phase-71-nav-breadcrumb-cleanup.md` — Evidence + review round.
2. `frontend/src/components/layout/Breadcrumbs.tsx`
3. `frontend/src/components/layout/Layout.tsx` — the learning-mode gate.
4. `docs/handoffs/2026-08-09-phase-70-lesson-transitions-pr-open.md` — for
   the carried items' full context.
